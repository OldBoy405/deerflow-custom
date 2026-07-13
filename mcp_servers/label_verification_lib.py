"""Core logic for label sticker verification (download + vision + JSON report)."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

MAX_IMAGE_BYTES = 20 * 1024 * 1024
REQUEST_TIMEOUT = 30
SUPPORTED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAGIC_BYTES = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"RIFF", "image/webp"),
]

VALID_RESULTS = {"PASS", "FAIL", "WARNING"}
VALID_STATUS = {"MATCH", "MISMATCH", "MISSING", "EXTRA", "UNCLEAR"}
VALID_SEVERITY = {"critical", "major", "minor", "info"}

DEFAULT_CHECK_PROMPT = (
    "核对贴纸全部可见内容，与标准版对比；"
    "识别标准有而实际缺失、实际多出、与标准不一致的项。"
)


@dataclass(frozen=True)
class VisionConfig:
    api_base: str
    api_key: str
    model: str
    timeout: float
    skills_root: Path


def _require_env(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or not str(value).strip():
        raise RuntimeError(f"Missing required env var: {name}")
    return str(value).strip()


def load_config() -> VisionConfig:
    api_key = _require_env("LABEL_VISION_API_KEY", os.getenv("OPENAI_API_KEY"))
    api_base = _require_env(
        "LABEL_VISION_API_BASE",
        os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    ).rstrip("/")
    model = os.getenv("LABEL_VISION_MODEL") or os.getenv("OPENAI_MODEL") or "qwen3-vl-flash"
    timeout = float(os.getenv("LABEL_VISION_TIMEOUT", "120"))
    skills_root = Path(
        os.getenv(
            "LABEL_VERIFICATION_SKILLS_ROOT",
            str(Path(__file__).resolve().parent.parent / "skills" / "custom" / "label-verification"),
        )
    )
    return VisionConfig(
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout=timeout,
        skills_root=skills_root,
    )


def _detect_mime(data: bytes) -> str | None:
    for magic, mime in MAGIC_BYTES:
        if data[: len(magic)] == magic:
            if mime == "image/webp" and (len(data) < 12 or data[8:12] != b"WEBP"):
                continue
            return mime
    return None


def download_image_bytes(url: str) -> tuple[bytes, str]:
    """Download image into memory. Returns (data, mime_type)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}. Only HTTP/HTTPS allowed.")

    last_error: str | None = None
    content_type = ""
    data: bytes | None = None

    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "DeerFlow-LabelVerification-MCP/1.0",
                    "Accept": "image/jpeg,image/png,image/webp,*/*",
                },
            )
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
                content_type = (response.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                data = response.read()
            break
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP error {e.code}: {e.reason} ({url})") from e
        except (urllib.error.URLError, TimeoutError) as e:
            last_error = (
                f"Request timed out after {REQUEST_TIMEOUT}s"
                if isinstance(e, TimeoutError)
                else f"URL error: {getattr(e, 'reason', e)}"
            )
            if attempt == 0:
                continue
            raise RuntimeError(f"{last_error} ({url})") from e

    if not data:
        raise RuntimeError(last_error or f"Download failed ({url})")
    if len(data) > MAX_IMAGE_BYTES:
        raise RuntimeError(f"Image too large: {len(data) / (1024 * 1024):.1f} MB (max 20 MB)")
    if not data:
        raise RuntimeError(f"Empty image ({url})")

    mime = _detect_mime(data)
    if mime is None and content_type in SUPPORTED_MIME_TYPES:
        mime = content_type
    if mime is None:
        guessed, _ = mimetypes.guess_type(url)
        if guessed in SUPPORTED_MIME_TYPES:
            mime = guessed
    if mime is None:
        raise RuntimeError(f"Unsupported image format from {url}")
    return data, mime


def _load_comparison_prompt(skills_root: Path, user_prompt: str) -> str:
    template_path = skills_root / "templates" / "comparison_prompt.md"
    if template_path.is_file():
        template = template_path.read_text(encoding="utf-8")
    else:
        template = (
            "图片1=标准贴纸，图片2=实际贴纸。\n核对范围：\n{user_provided_prompt}\n"
            "输出仅有 JSON：overall_result, checks, differences_summary；"
            "checks 项若有 notes，notes 必须使用中文。"
        )
    prompt = user_prompt.strip() or DEFAULT_CHECK_PROMPT
    return template.replace("{user_provided_prompt}", prompt)


def _is_valid_check(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    for key in ("field", "expected", "actual", "status", "match", "severity"):
        if key not in item:
            return False
    if not isinstance(item["field"], str) or not item["field"]:
        return False
    if item["status"] not in VALID_STATUS:
        return False
    if item["severity"] not in VALID_SEVERITY:
        return False
    if not isinstance(item["match"], bool):
        return False
    if item["match"] != (item["status"] == "MATCH"):
        return False
    return True


def is_valid_report(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    if set(obj.keys()) - {"overall_result", "checks", "differences_summary"}:
        return False
    if obj.get("overall_result") not in VALID_RESULTS:
        return False
    checks = obj.get("checks")
    if not isinstance(checks, list) or not checks:
        return False
    if not all(_is_valid_check(item) for item in checks):
        return False
    return isinstance(obj.get("differences_summary"), str)


def sanitize_report(obj: dict[str, Any]) -> dict[str, Any]:
    checks = []
    for item in obj["checks"]:
        row = {
            k: item[k]
            for k in ("field", "expected", "actual", "status", "match", "severity")
            if k in item
        }
        if item.get("notes") is not None:
            row["notes"] = item["notes"]
        checks.append(row)
    return {
        "overall_result": obj["overall_result"],
        "checks": checks,
        "differences_summary": obj["differences_summary"],
    }


def extract_json_report(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if is_valid_report(obj):
            return sanitize_report(obj)
    except json.JSONDecodeError:
        pass

    for block in re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text):
        try:
            obj = json.loads(block)
            if is_valid_report(obj):
                return sanitize_report(obj)
        except json.JSONDecodeError:
            continue

    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if is_valid_report(obj):
                            return sanitize_report(obj)
                    except json.JSONDecodeError:
                        break
                    break
    return None


def _call_vision_api(
    cfg: VisionConfig,
    system_text: str,
    user_text: str,
    standard_b64: str,
    standard_mime: str,
    actual_b64: str,
    actual_mime: str,
) -> str:
    payload = {
        "model": cfg.model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_text},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{standard_mime};base64,{standard_b64}"},
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{actual_mime};base64,{actual_b64}"},
                    },
                ],
            },
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{cfg.api_base}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Vision API HTTP {e.code}: {detail}") from e
    except Exception as e:
        raise RuntimeError(f"Vision API request failed: {e}") from e

    data = json.loads(raw)
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        content = "\n".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("Vision API returned empty content")
    return content


def verify_labels(
    standard_image_url: str,
    actual_image_url: str,
    verification_prompt: str = "",
    *,
    config: VisionConfig | None = None,
) -> dict[str, Any]:
    """Download two label images, compare via vision model, return report dict."""
    cfg = config or load_config()
    standard_data, standard_mime = download_image_bytes(standard_image_url)
    actual_data, actual_mime = download_image_bytes(actual_image_url)

    comparison_prompt = _load_comparison_prompt(cfg.skills_root, verification_prompt)
    system_text = (
        "你是产品质量检验员。根据两张标签贴纸图片完成对比，"
        "最终回复有且仅有一个 JSON 对象（无 Markdown、无说明文字）。"
        "checks 中若有 notes 字段，notes 的值必须使用中文；无补充说明时可省略 notes。"
    )
    user_text = (
        f"{comparison_prompt}\n\n"
        "图片顺序：第一张=标准贴纸，第二张=实际贴纸。\n"
        "字段定义见 report_schema：overall_result, checks, differences_summary。"
    )

    std_b64 = base64.b64encode(standard_data).decode("ascii")
    act_b64 = base64.b64encode(actual_data).decode("ascii")

    last_content = ""
    for attempt in range(2):
        content = _call_vision_api(cfg, system_text, user_text, std_b64, standard_mime, act_b64, actual_mime)
        last_content = content
        report = extract_json_report(content)
        if report is not None:
            return report
        user_text += "\n\n上次输出不符合 JSON schema，请仅输出合法 JSON，不要任何其他文字。"

    raise RuntimeError(f"Vision model did not return valid report JSON. Last output: {last_content[:500]}")
