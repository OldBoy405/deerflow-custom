# DeerFlow 二次开发记录

## 基本信息

| 项 | 值 |
|----|-----|
| 官方仓库 | https://github.com/bytedance/deer-flow |
| 二开仓库 | https://github.com/OldBoy405/deerflow-custom |
| 主开发分支 | `custom/main` |
| 产品名 | （待填写） |
| 是否对外分发 | （是/否，待填写） |
| 上次提交 | `97f9794`（2026-07-13 14:45，`添加 DeerFlow 二开记录`） |
| 相对上游基线 | `2b79526`（2026-06-10，上游 `main` 当时 HEAD；`Merge origin/main into main` → `1268c34`） |
| 工作区状态（截至 2026-07-18） | 已推送二开相对基线约 **30 个非产物文件**（代码/脚本/Compose/MCP/文档）；另含 `.qoder/`、`graphify-out/` 等大量知识库/图分析产物。本地 Git object 曾损坏，对比以 GitHub `custom/main` 为准。 |

> **说明**：GitHub 上 `deerflow-custom` 未标记为官方 fork（`fork: false`），以独立仓库 + `upstream` remote 跟踪官方。合并时用 `git fetch upstream` + `git merge upstream/main`（或 rebase）。

---

## 上游代码改动（落在官方目录树内）

> **范围**：官方仓库已有路径上的修改（`backend/`、`frontend/src/`、`docker/`、`scripts/`、`.env.example` 等）。不含 `mcp_servers/`、`.qoder/`、`graphify-out/`、根目录架构讲解页等二开专属树。

### 合并冲突总则

执行 `git merge upstream/main` 时，对本节所列文件的**默认原则**：

1. **两边都保留**——不采用「取上游覆盖二开」或「取二开覆盖上游」的二选一。
2. **逻辑整合**——以上游新增/重构为基底，再把二开语义**重新贴回**正确位置；上游重命名变量/函数时跟着改名。
3. **加法优先**——二开以「新行为 / 新可选能力 / 新挂载 / 新 env」为主；未使用新能力时尽量与上游行为一致。
4. **IM 通道慎重**——`feishu.py` / `manager.py` 改动面大，合并后必跑 `backend/tests/test_channels.py`。
5. **合并后必跑**——`cd backend && make lint && make test`；前端相关改动再跑 `cd frontend && pnpm lint && pnpm typecheck`。

---

### 上游改动清单

#### A. IM 通道（Feishu / Channel Manager）— 约 2026-05 ~ 06，随 `673f00d` / `1268c34` 进入主线

| 日期（约） | 文件 / 符号位置 | 改动摘要 | 冲突整合原则 |
|------------|----------------|----------|--------------|
| 2026-05~06 | `backend/app/channels/feishu.py` · `_split_card_text` / `_CARD_TEXT_SOFT_LIMIT` | 长回复按 ~2800 字在安全边界切片，避免飞书卡片前端卡死 | 保留常量与切片函数；上游若改发卡片路径，把 `_patch_then_append` 接线贴回 |
| 2026-05~06 | `feishu.py` · `_sanitize_card_markdown` | 远程 `![alt](url)` 改写成普通链接，避免飞书 `230099` 整卡创建失败 | 保留正则与替换；上游 `_build_card_content` 重构时仍先 sanitize 再塞 markdown |
| 2026-05~06 | `feishu.py` · `_log_lark_error` / `_update_card` 返回 bool | 检查 OpenAPI `success()`；patch 失败时返回 False | 保留返回值语义；调用方按失败走 follow-up 卡片 |
| 2026-05~06 | `feishu.py` · `_patch_then_append` | 先 PATCH 首卡（过长则预览头），余量按序 reply 追加卡 | **整段方法保留**；与上游流式更新逻辑并列整合 |
| 2026-05~06 | `backend/app/channels/manager.py` · `_extract_response_text` | 只取最近 human 之后的本轮消息；拼接本轮全部非空 AI 文本；澄清工具优先；去掉 `[LOOP DETECTED]` 行 | 保留本轮边界 + 多段拼接；上游若改 message 形状，适配 `_ai_message_plain_text` |
| 2026-05~06 | `manager.py` · `_download_remote_chart_attachments` 等 | 从回复文本识别 alipayobjects 图表 URL，下载到 thread outputs，供 IM `send_file` | 整块保留；仅 IM 路径调用，不影响 Web |
| 2026-05~06 | `backend/tests/test_channels.py` | `_extract_response_text` 多段 AI / 澄清 / 边界用例扩展 | 两边用例都保留 |

#### B. 配置 / Sandbox / 中间件 — 约 2026-05 ~ 06

| 日期（约） | 文件 / 符号位置 | 改动摘要 | 冲突整合原则 |
|------------|----------------|----------|--------------|
| 2026-05~06 | `backend/packages/harness/deerflow/config/app_config.py` · `_expand_braced_env_vars` | 支持 `${VAR}` 内嵌展开（Postgres DSN 等）；缺 env 抛 `ValueError` | 保留 `${}` 分支；`$NAME` 整串替换仍以上游为准 |
| 2026-05~06 | `backend/tests/test_app_config_env_expand.py` · **新文件** | `${}` / `$NAME` / 缺变量回归 | 新文件保留 |
| 2026-05~06 | `deerflow/sandbox/tools.py` · `validate_local_tool_path` | 允许精确 `/mnt/user-data`（不仅带尾斜杠的前缀） | 保留 `path == VIRTUAL_PATH_PREFIX` 分支 |
| 2026-05~06 | `sandbox/tools.py` · `_validate_resolved_user_data_path` | 三目录同父时把 `user-data/` 父目录加入 allowed_roots | 保留父目录放行；上游改路径布局时按新布局重贴 |
| 2026-05~06 | `dangling_tool_call_middleware.py` | 增加 `AIMessage` import（供类型/扫描语义一致） | 保留 import；上游若已 import 则去重即可 |

#### C. Docker / 部署脚本 — 约 2026-05 ~ 07-13

| 日期（约） | 文件 / 符号位置 | 改动摘要 | 冲突整合原则 |
|------------|----------------|----------|--------------|
| 2026-05~06 | `docker/docker-compose.yaml` / `docker-compose-dev.yaml` | 增加 **profile `postgres`** 的 `postgres:16-alpine`；gateway 注入 `DEER_FLOW_POSTGRES_*`；`depends_on` required:false；dev 挂载 `../mcp_servers/` → `/app/backend/mcp_servers/` | 整块 postgres 服务保留；上游加 service 时并列；**勿删** mcp_servers 挂载 |
| 2026-05~06 | `scripts/deploy.sh` / `scripts/docker.sh` | `apply_compose_postgres_profile_from_config`：读 `config.yaml` checkpointer.type；Compose V2/V1 兼容；`down` 时配置路径改回仓库根 `config.yaml` | 保留 profile 探测与 `compose_run` 数组写法；上游改 compose 调用方式时迁入同等探测 |
| 2026-07-13 | `scripts/compose_detect.sh` · **新文件** | 抽出 UV_EXTRAS / postgres profile 探测（拟共享） | 新文件保留；**注意**：当前 `deploy.sh`/`docker.sh` 仍内联同类逻辑，尚未 `source` 本文件——合并时不要误删内联实现，除非先完成接线 |
| 2026-05~06 | `backend/Dockerfile` | 安装 unixODBC + msodbcsql18；`UV_HTTP_TIMEOUT`/`UV_CONCURRENT_DOWNLOADS`；生产 stage 同样装 ODBC 运行时；**同步命令去掉 `${UV_EXTRAS:+--extra}`**（缓存 mount 亦注释） | 保留 ODBC 层与超时 env；上游恢复 `UV_EXTRAS` 时：ODBC 层与 extras 并存，不要用上游整文件盖掉 ODBC |
| 2026-05~06 | `.env.example` | Postgres / SQL Server MCP 占位注释 | 保留注释块；上游新增 env 说明时并列 |

#### D. 前端消息 UI — 约 2026-05 ~ 06

| 日期（约） | 文件 / 符号位置 | 改动摘要 | 冲突整合原则 |
|------------|----------------|----------|--------------|
| 2026-05~06 | `frontend/src/core/messages/utils.ts` · `getMessageGroups` | 孤儿 `tool` 消息收入 `assistant:processing` 组，不再仅 `console.error` | 保留兜底分组；上游改 MessageGroup 类型时对齐 type 字面量 |
| 2026-05~06 | `frontend/src/components/workspace/messages/message-group.tsx` · `convertToSteps` | 把未覆盖的 tool 结果补进 CoT steps | 保留补扫循环；上游改 CoTStep 形状时字段对齐 |

---

### 上游改动按主题索引

| 主题 | 涉及文件 | 首次进入主线（约） |
|------|----------|-------------------|
| 飞书长卡片切片 / 远程图消毒 / patch 失败回退 | `feishu.py` + `test_channels.py` | 2026-05~06 |
| IM 本轮全文拼接 + 远程图表下载附件 | `manager.py` + `test_channels.py` | 2026-05~06 |
| `${VAR}` 配置展开 | `app_config.py` + `test_app_config_env_expand.py` | 2026-05~06 |
| `/mnt/user-data` 根路径与父目录放行 | `sandbox/tools.py` | 2026-05~06 |
| Compose 捆绑 Postgres + MCP 挂载 | `docker-compose*.yaml`、`deploy.sh`、`docker.sh` | 2026-05~06 |
| 镜像 ODBC / 慢网 UV | `backend/Dockerfile` | 2026-05~06 |
| 前端孤儿 tool 消息可渲染 | `utils.ts`、`message-group.tsx` | 2026-05~06 |

---

## 二开专属文件（不动上游契约）

> **原则**：业务 MCP、方案文档、知识库、图分析产物默认 **零上游改动**；通过 `extensions_config.json` / Compose 挂载消费。

| 日期（约） | 文件/目录 | 说明 |
|------------|-----------|------|
| 2026-05~06 | `mcp_servers/sqlserver_mcp_server.py` | SQL Server 只读查询 MCP（FastMCP + SQLAlchemy）；禁写 SQL |
| 2026-05~06 | `mcp_servers/rag_kb_server.py` | Postgres RAG 知识库检索 MCP（psycopg + embedding） |
| 2026-05~06 | `mcp_servers/label_verification_mcp_server.py` + `label_verification_lib.py` | 产品标签贴纸视觉核对 MCP |
| 2026-05~06 | `docs/` 下权限/记忆/RAG/SQL 方案与流程图 | 二开设计文档（含 `docs/sql/authz_init.sql`） |
| 2026-05~06 | `backend/docs/*_ZH.md` | 中文配置/MCP/Memory 说明 |
| 2026-05~06 | `人机协作置信度分层.md`、`项目代码逻辑讲解.html` | 根目录讲解材料 |
| 2026-07-13 | `CUSTOM.md` | 本文件 |
| 2026-07-13 | `CLAUDE.md` | 本仓库 Agent 指引（相对当时上游基线为新增；合并时若上游已有同名文件，做内容合并而非覆盖） |
| 2026-07-13 | `.qoder/` | Qoder 知识库 / repowiki / plans |
| 2026-07-13 | `backend/graphify-out/`、`frontend/graphify-out/`、`graphify-out/` | graphify 分析产物（可重建，合并冲突时通常可丢弃再生） |
| 2026-07-13 | `.github/ISSUE_TEMPLATE/runtime-information.yml` | 运行时信息 issue 模板 |

---

## 我修复的上游 Bug / 体验问题

| 日期（约） | 文件 / 符号位置 | 问题描述 | 根因 | 修复 | 影响面 |
|------------|----------------|----------|------|------|--------|
| 2026-05~06 | `feishu.py` 卡片 patch | 长 markdown 或远程图片导致飞书卡片静默失败/停在旧快照 | 未检查 API success；远程 `![](url)` 触发 230099；超长正文超过前端可渲染预算 | sanitize + soft limit 切片 + patch 失败则追加卡 | 飞书 IM 长回复 / 含图回复 |
| 2026-05~06 | `manager.py` `_extract_response_text` | IM 只显示本轮最后一句短 AI，丢掉同轮前面的表格/分析 | 原实现只取「最后一条」AI | 本轮内拼接全部非空 AI 段 | 所有走 Channel Manager 的 IM |
| 2026-05~06 | `frontend/.../utils.ts` | 历史/重载后 tool 消息落在 processing 组外，UI 丢工具结果 | 流顺序与分组假设过严 | 孤儿 tool 收入 processing 组 + CoT 补扫 | Web 工作区消息流 |
| 2026-05~06 | `sandbox/tools.py` | `ls /mnt/user-data` 被拒 | 仅允许带 `/` 的前缀匹配 | 允许精确前缀；同父 `user-data` 根放行 | 本地 sandbox 文件工具 |

---

## 我新增的能力

| 日期（约） | 能力 | 位置 |
|------------|------|------|
| 2026-05~06 | Compose 可选捆绑 PostgreSQL（profile） | `docker/docker-compose*.yaml` + `scripts/*` |
| 2026-05~06 | 配置字符串 `${ENV}` 展开 | `app_config.py` |
| 2026-05~06 | IM 自动下载 AntV/支付宝对象存储图表为附件 | `manager.py` |
| 2026-05~06 | SQL Server / RAG KB / 标签核对 MCP | `mcp_servers/` |
| 2026-05~06 | 后端镜像 ODBC（SQL Server 驱动） | `backend/Dockerfile` |
| 2026-07-13 | 二开记录 / Agent 指引 / 知识库 | `CUSTOM.md`、`CLAUDE.md`、`.qoder/` |

---

## 我故意删除或禁用的内容

| 日期（约） | 路径/配置 | 原因 |
|------------|-----------|------|
| 2026-05~06 | `backend/Dockerfile` 构建期 `uv sync ${UV_EXTRAS:+--extra …}` 与 cache mount | 慢网/ODBC 场景改为显式超时与无 cache 的 `uv sync`；**副作用**：镜像构建不再按 `UV_EXTRAS` 装 postgres extra——若上游依赖该机制，合并后需把 extras 接线与 ODBC 并存恢复 |
| 2026-05~06 | SQL Server MCP 写语句 | `_WRITE_SQL_RE` 拦截，只读查询 |

---

## 合并官方记录

| 日期 | 官方版本/commit | 冲突 | 备注 |
|------|----------------|------|------|
| 2026-05-15 | 远程变更（`673f00d` / `990d714`） | 有（提交信息含 resolve conflicts） | 二开能力进入本地主线 |
| 2026-06-10 | `2b79526`（#3471）→ merge `1268c34` | 有 | 相对第二父（纯上游）保留约 58 文件二开差异（含脚本/文档/讲解页） |
| 2026-07-13 | — | — | `a3eec37`/`97f9794` 追加 CUSTOM/CLAUDE/.qoder/graphify 等；**尚未**再 merge 更新后的 `upstream/main`（上游已前进至 2026-07 一带） |

---

## 后续待办

| 待办项 | 备注 |
|--------|------|
| **同步上游 main** | 二开停在 2026-06-10 基线，落后官方约一个月+；合并时按本文件「冲突整合原则」逐主题贴回，重点 `feishu.py`/`manager.py`/`Dockerfile`/Compose |
| **`compose_detect.sh` 接线** | 已抽出共享探测脚本，但 `deploy.sh`/`docker.sh` 仍内联；应改为 `source` 单一实现，避免双份逻辑漂移 |
| **Dockerfile `UV_EXTRAS` 恢复评估** | 确认生产/dev 是否仍需 `--extra postgres`；若需要，与 ODBC 层一起恢复 |
| **产物是否入库** | `.qoder/`、`graphify-out/` 体积大；评估是否改 `.gitignore` + 本地生成，减小 merge 噪声 |
| **补测试** | 飞书 `_split_card_text` / sanitize、图表下载、sandbox 父目录放行等可再补单测（现有以 `test_channels` + `test_app_config_env_expand` 为主） |
| **产品名 / 是否对外分发** | 填基本信息表 |
| **修复本地 Git 对象库** | 工作区曾出现 `bad object HEAD`；整理记录时用浅克隆对比。建议 `git fetch --refetch` 或重 clone 后再开发 |

---

## 合并后快速验证清单

```bash
# 后端
cd backend && make lint && make test
# 至少关注：
#   tests/test_channels.py
#   tests/test_app_config_env_expand.py

# 前端（若碰了 messages）
cd frontend && pnpm lint && pnpm typecheck

# Compose postgres profile（config.yaml checkpointer.type: postgres）
# make docker-start / ./scripts/docker.sh 应自动带上 COMPOSE_PROFILES=postgres
```
