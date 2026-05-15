# DeerFlow RAG 相关说明（MCP 接入版）

本文整理当前项目的 RAG 现状、推荐架构、MCP 接入方案、控 token 规范、接口契约与落地文件，便于快速实施。

---

## 1. 当前项目是否内置完整 RAG

结论：**当前项目不内置“一站式 RAG 引擎”**（即文档切分、embedding、向量入库、召回链路的完整内建实现）。

已具备能力：

- 文件上传与可选文档转 Markdown
- Agent 通过 `read_file` / `grep` / `glob` 读取和检索已上传文件
- MCP 工具扩展能力（可接入外部知识检索系统）

因此，推荐通过 MCP server 引入 RAG 能力。

---

## 2. 两种接入方式对比（MCP vs Python Tool）

### 2.1 推荐结论

- **生产优先**：MCP server
- **快速 PoC**：Python tool

### 2.2 优劣对比

- **MCP server**
  - 优点：解耦、可复用、独立扩缩容、权限边界清晰
  - 缺点：多一层服务与部署，排障链路稍长
- **Python tool**
  - 优点：开发快、调试直观、改动成本低
  - 缺点：与主应用耦合强，复用差，后续治理成本高

### 2.3 token 角度

- 一般情况下 **MCP 更省 token**（尤其工具多时配合按需发现）
- 真正 token 大头是“返回内容长度”，与接入方式无关

---

## 3. 推荐的 RAG MCP 实现路径

1. 将 RAG 能力做成 MCP server（至少 2 个工具）
   - `search_knowledge`：首轮检索，返回短摘要和 `source_id`
   - `expand_sources`：按 `source_id` 二次拉取正文证据
2. 在 `extensions_config.json` 注册 MCP server
3. 重启 DeerFlow，确认 MCP 工具已可调用
4. 在 Guardrail 中对工具和知识资源做权限控制（部门/角色）
5. 按“摘要优先 -> 按需展开”链路联调

---

## 4. MCP 配置示例（extensions_config.json）

`stdio` 本地启动示例：

```json
{
  "mcpInterceptors": [],
  "mcpServers": {
    "rag-kb": {
      "enabled": true,
      "type": "stdio",
      "command": "python",
      "args": ["./mcp_servers/rag_kb_server.py"],
      "env": {
        "RAG_DB_URL": "$RAG_DB_URL",
        "RAG_EMBEDDING_MODEL": "$RAG_EMBEDDING_MODEL",
        "RAG_DEFAULT_NAMESPACE": "corp.cn"
      },
      "description": "RAG knowledge base MCP server (search + expand)"
    }
  },
  "skills": {}
}
```

`http` 远程部署示例：

```json
{
  "mcpInterceptors": [],
  "mcpServers": {
    "rag-kb": {
      "enabled": true,
      "type": "http",
      "url": "https://rag-mcp.example.com/mcp",
      "env": {},
      "description": "Remote RAG MCP server"
    }
  },
  "skills": {}
}
```

---

## 5. 已落地代码（pgvector 真实查询版）

已新增文件：

- `mcp_servers/rag_kb_server.py`

该脚本包含：

- `search_knowledge`：embedding + pgvector 相似度检索 + 简单重排 + token 预算裁剪
- `expand_sources`：按 `source_id` 拉取正文证据，支持预算控制/去重/截断

### 5.1 关键环境变量

- `RAG_DB_URL`（必填）
- `RAG_EMBEDDING_API_KEY`（必填）
- `RAG_EMBEDDING_MODEL`（默认：`text-embedding-3-small`）
- `RAG_EMBEDDING_DIMENSIONS`（默认：`1536`）
- `RAG_EMBEDDING_API_BASE`（默认：`https://api.openai.com/v1`）
- `RAG_TABLE_NAME`（默认：`rag_chunks`）
- `RAG_EMBEDDING_COLUMN`（默认：`embedding`）
- `RAG_DEFAULT_NAMESPACE`（默认：`corp.cn`）
- `RAG_DEFAULT_KB_ID`（默认：`default_kb`）

### 5.2 默认依赖的表字段（rag_chunks）

- `namespace text`
- `kb_id text`
- `chunk_id text`
- `title text`
- `content text`
- `metadata jsonb`
- `embedding vector(<dim>)`

---

## 6. 检索控 token 的 6 条硬规则

1. **先小后大的 topK**：首轮 `3~5`，不够再扩 `8~12`
2. **限制 chunk 大小**：推荐 `300~500 tokens`，overlap `50~80`
3. **先摘要后原文**：首轮只回摘要和引用标识
4. **二跳检索**：首轮粗召回，次轮再精读展开
5. **预算闸门**：每轮设置检索 token 上限（如 `1800`）
6. **去重合并**：相似证据去重，减少重复上下文

建议默认参数：

- `topK_first=4`
- `topK_second=10`
- `final_evidence_count=4`
- `chunk_size=400`
- `chunk_overlap=64`
- `max_retrieval_tokens=1800`

---

## 7. 接口契约建议（Schema）

建议按两阶段返回：

- 阶段一：`Token-Efficient Retrieval Response`
  - 返回 `hits[].summary` + `source_id`
- 阶段二：`expand_sources`
  - 按 `source_ids` 拉正文，严格执行 `max_total_tokens`

对应配套内容已给出：

- 检索结果 JSON Schema（摘要优先）
- `expand_sources` 请求/响应 JSON Schema
- 对应 TypeScript 类型定义

---

## 8. source_id 与资源命名规范

建议统一：

- 工具：`tool:<tool_name>`
- 知识库：`kb:<namespace>:<kb_id>#<chunk_id>`
- MCP 工具：`mcp:<server>:<tool>`

`source_id` 示例：

- `kb:corp.cn.finance:kb_invoice_001#c12`

好处：

- 便于 `expand_sources` 回查
- 便于权限策略按资源匹配
- 便于审计与追踪

---

## 9. 与权限控制的衔接建议

结合 `MyGuardrailProvider`：

- 对工具级别控制：
  - `mcp:rag-kb:search_knowledge`
  - `mcp:rag-kb:expand_sources`
- 对资源级别控制：
  - 从工具入参提取 `namespace/kb_id/source_id`
  - 按部门/角色策略判定
- 冲突策略：
  - 默认拒绝
  - deny 优先于 allow

---

## 10. 最短联调步骤

1. 配置 `extensions_config.json`，启用 `rag-kb`
2. 配置环境变量并重启 DeerFlow
3. 对话触发 `search_knowledge`
4. 再触发 `expand_sources`
5. 验证 token 预算与截断行为
6. 验证不同角色对知识资源的访问控制

---

## 11. 常见问题与排查

- **工具没出现**
  - 检查 `extensions_config.json` 是否启用 + 重启服务
- **embedding 报错**
  - 检查 `RAG_EMBEDDING_API_KEY` / 模型维度配置
- **pgvector 维度不一致**
  - `RAG_EMBEDDING_DIMENSIONS` 必须与表中向量列一致
- **token 过高**
  - 降低 `topk`，缩短摘要，严格限制二次拉取预算
- **权限未生效**
  - 检查 Guardrail 是否开启、是否正确解析 `namespace/kb_id/source_id`

---

## 12. 后续增强建议

- 引入更强 reranker（交叉编码器）
- 增加多路召回（向量 + 关键词）融合
- 增加缓存层（query->source_ids）
- 完整接入审计指标（命中率、拒绝率、平均 token）
- 增加 `rag_chunks` 建表和向量索引脚本（ivfflat/hnsw）

