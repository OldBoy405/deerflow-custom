from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal

import psycopg
from mcp.server.fastmcp import FastMCP
from psycopg.rows import dict_row

mcp = FastMCP("rag-kb")

RetrievalStage = Literal["first_hop", "second_hop"]
QuoteMode = Literal["snippet", "paragraph", "mixed"]


@dataclass(frozen=True)
class RagConfig:
    db_url: str
    table_name: str
    embedding_column: str
    embedding_dimensions: int
    embedding_provider: str
    embedding_model: str
    embedding_api_key: str
    embedding_api_base: str
    default_namespace: str
    default_kb_id: str


def _require_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not value.strip():
        raise RuntimeError(f"Missing required env var: {name}")
    return value.strip()


def _load_config() -> RagConfig:
    return RagConfig(
        db_url=_require_env("RAG_DB_URL"),
        table_name=os.getenv("RAG_TABLE_NAME", "rag_chunks"),
        embedding_column=os.getenv("RAG_EMBEDDING_COLUMN", "embedding"),
        embedding_dimensions=int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "1536")),
        embedding_provider=os.getenv("RAG_EMBEDDING_PROVIDER", "openai").lower(),
        embedding_model=_require_env("RAG_EMBEDDING_MODEL", "text-embedding-3-small"),
        embedding_api_key=_require_env("RAG_EMBEDDING_API_KEY"),
        embedding_api_base=os.getenv("RAG_EMBEDDING_API_BASE", "https://api.openai.com/v1").rstrip("/"),
        default_namespace=os.getenv("RAG_DEFAULT_NAMESPACE", "corp.cn"),
        default_kb_id=os.getenv("RAG_DEFAULT_KB_ID", "default_kb"),
    )


CONFIG = _load_config()


def _estimate_tokens(text: str) -> int:
    # Lightweight approximation to keep budgeting deterministic.
    return max(1, len(text) // 4)


def _embedding_to_pgvector_literal(values: list[float]) -> str:
    # pgvector accepts text literal format: [0.1,0.2,...]
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def _openai_embed(text: str) -> list[float]:
    payload = json.dumps({"input": text, "model": CONFIG.embedding_model}).encode("utf-8")
    req = urllib.request.Request(
        url=f"{CONFIG.embedding_api_base}/embeddings",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CONFIG.embedding_api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Embedding API HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"Embedding API request failed: {e}") from e

    data = json.loads(body)
    embedding = data.get("data", [{}])[0].get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("Embedding API returned invalid payload")
    return [float(v) for v in embedding]


def _embed_query(query: str) -> list[float]:
    if CONFIG.embedding_provider != "openai":
        raise RuntimeError(f"Unsupported embedding provider: {CONFIG.embedding_provider}")
    vec = _openai_embed(query)
    if len(vec) != CONFIG.embedding_dimensions:
        raise RuntimeError(
            f"Embedding dimensions mismatch: got {len(vec)}, expected {CONFIG.embedding_dimensions}. "
            "Set RAG_EMBEDDING_DIMENSIONS to match your embedding model."
        )
    return vec


def _connect() -> psycopg.Connection:
    return psycopg.connect(CONFIG.db_url, row_factory=dict_row)


def _to_resource_id(namespace: str, kb_id: str, chunk_id: str) -> str:
    return f"kb:{namespace}:{kb_id}#{chunk_id}"


def _parse_resource_id(source_id: str) -> tuple[str, str, str]:
    # kb:<namespace>:<kb_id>#<chunk_id>
    if not source_id.startswith("kb:"):
        raise ValueError(f"Invalid source_id format: {source_id}")
    body = source_id[3:]
    if "#" not in body:
        raise ValueError(f"Invalid source_id format: {source_id}")
    left, chunk_id = body.split("#", 1)
    ns, kb_id = left.rsplit(":", 1)
    return ns, kb_id, chunk_id


def _apply_simple_rerank(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Tiny lexical boost on top of vector similarity.
    query_terms = {t.lower() for t in re.findall(r"[a-zA-Z0-9_\u4e00-\u9fa5]+", query) if len(t) >= 2}
    for row in rows:
        haystack = f"{row.get('title', '')}\n{row.get('content', '')}".lower()
        overlap = sum(1 for t in query_terms if t in haystack)
        row["_rank_score"] = float(row["score"]) + overlap * 0.01
    rows.sort(key=lambda x: x["_rank_score"], reverse=True)
    return rows


@mcp.tool()
def search_knowledge(
    query: str,
    topk: int = 4,
    max_total_tokens: int = 1800,
    namespace: str | None = None,
    kb_id: str | None = None,
    stage: RetrievalStage = "first_hop",
) -> dict[str, Any]:
    """Search knowledge chunks from pgvector and return compact summaries."""
    if not query.strip():
        raise ValueError("query must not be empty")

    namespace = namespace or CONFIG.default_namespace
    kb_id = kb_id or CONFIG.default_kb_id
    topk = max(1, min(int(topk), 20))

    embedding = _embed_query(query)
    embedding_literal = _embedding_to_pgvector_literal(embedding)

    sql = f"""
    select
      namespace,
      kb_id,
      chunk_id,
      title,
      content,
      metadata,
      1 - ({CONFIG.embedding_column} <=> %s::vector) as score
    from {CONFIG.table_name}
    where namespace = %s
      and kb_id = %s
    order by {CONFIG.embedding_column} <=> %s::vector
    limit %s
    """

    with _connect() as conn, conn.cursor() as cur:
        cur.execute(sql, (embedding_literal, namespace, kb_id, embedding_literal, topk * 2))
        rows = cur.fetchall()

    normalized: list[dict[str, Any]] = []
    for row in rows:
        content = row.get("content") or ""
        summary = content[:240] + ("..." if len(content) > 240 else "")
        normalized.append(
            {
                "namespace": row["namespace"],
                "kb_id": row["kb_id"],
                "chunk_id": row["chunk_id"],
                "title": row.get("title") or f"Chunk {row['chunk_id']}",
                "content": content,
                "summary": summary,
                "score": max(0.0, min(1.0, float(row["score"]))),
                "metadata": row.get("metadata") or {},
            }
        )

    reranked = _apply_simple_rerank(query, normalized)[:topk]

    hits: list[dict[str, Any]] = []
    token_used = 0
    for item in reranked:
        if token_used >= max_total_tokens:
            break
        source_id = _to_resource_id(item["namespace"], item["kb_id"], item["chunk_id"])
        hit = {
            "source_id": source_id,
            "title": item["title"],
            "score": round(item["score"], 4),
            "summary": item["summary"],
            "evidence_ref": {"locator_type": "chunk_id", "locator": item["chunk_id"]},
        }
        hit_tokens = _estimate_tokens(hit["summary"]) + 40
        if token_used + hit_tokens > max_total_tokens:
            break
        token_used += hit_tokens
        hits.append(hit)

    return {
        "query": query,
        "retrieval": {
            "stage": stage,
            "topk_requested": topk,
            "topk_returned": len(hits),
            "token_budget": max_total_tokens,
            "token_used": token_used,
            "has_more": len(rows) > len(hits),
        },
        "hits": hits,
        "next_actions": {
            "can_expand": len(hits) > 0,
            "expand_api_hint": "expand_sources(source_ids, max_total_tokens=800)",
            "recommended_source_ids": [h["source_id"] for h in hits[:3]],
        },
        "debug": {
            "retriever": "pgvector-cosine",
            "ranker": "vector+lexical",
        },
    }


@mcp.tool()
def expand_sources(
    query: str,
    source_ids: list[str],
    max_total_tokens: int,
    max_tokens_per_source: int = 600,
    quote_mode: QuoteMode = "mixed",
    deduplicate: bool = True,
    include_citations: bool = True,
) -> dict[str, Any]:
    """Fetch full evidence blocks by source IDs with strict token budget."""
    if not source_ids:
        return {
            "query": query,
            "budget": {
                "max_total_tokens": max_total_tokens,
                "used_tokens": 0,
                "remaining_tokens": max_total_tokens,
                "truncated": False,
            },
            "expanded": [],
            "dropped": [],
            "next_actions": {"can_continue_expand": False, "suggested_followup": "source_ids is empty"},
        }

    used_tokens = 0
    expanded: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    seen_texts: set[str] = set()

    with _connect() as conn, conn.cursor() as cur:
        for source_id in source_ids[:5]:
            try:
                ns, kid, chunk_id = _parse_resource_id(source_id)
            except ValueError:
                dropped.append({"source_id": source_id, "reason": "not_found"})
                continue

            cur.execute(
                f"""
                select namespace, kb_id, chunk_id, title, content, metadata
                from {CONFIG.table_name}
                where namespace = %s and kb_id = %s and chunk_id = %s
                limit 1
                """,
                (ns, kid, chunk_id),
            )
            row = cur.fetchone()
            if not row:
                dropped.append({"source_id": source_id, "reason": "not_found"})
                continue

            content = (row.get("content") or "").strip()
            if not content:
                dropped.append({"source_id": source_id, "reason": "not_found"})
                continue

            if deduplicate and content in seen_texts:
                dropped.append({"source_id": source_id, "reason": "duplicate"})
                continue
            seen_texts.add(content)

            if quote_mode == "snippet":
                text = content[:400]
            elif quote_mode == "paragraph":
                text = content[:1200]
            else:
                text = content[:800]

            text_token_est = min(max_tokens_per_source, _estimate_tokens(text))
            if used_tokens + text_token_est > max_total_tokens:
                dropped.append({"source_id": source_id, "reason": "budget_exceeded"})
                continue

            used_tokens += text_token_est
            expanded.append(
                {
                    "source_id": source_id,
                    "score": 0.9,
                    "content_blocks": [
                        {
                            "block_id": f"{chunk_id}-b1",
                            "text": text,
                            "token_estimate": text_token_est,
                            "locator": {"type": "chunk_id", "value": chunk_id},
                        }
                    ],
                    "citations": (
                        [
                            {
                                "id": f"cit-{chunk_id}",
                                "label": row.get("title") or f"{ns}/{kid}#{chunk_id}",
                            }
                        ]
                        if include_citations
                        else []
                    ),
                }
            )

    return {
        "query": query,
        "budget": {
            "max_total_tokens": max_total_tokens,
            "used_tokens": used_tokens,
            "remaining_tokens": max(0, max_total_tokens - used_tokens),
            "truncated": any(d["reason"] == "budget_exceeded" for d in dropped),
        },
        "expanded": expanded,
        "dropped": dropped,
        "next_actions": {
            "can_continue_expand": len(dropped) > 0,
            "suggested_followup": "increase max_total_tokens or reduce source_ids",
        },
        "debug": {
            "dedup_ratio": (len(dropped) / len(source_ids)) if source_ids else 0.0,
        },
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")

