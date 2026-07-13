# 配置指南

本指南说明如何为当前环境配置 DeerFlow。

## 配置版本

`config.example.yaml` 中包含 `config_version` 字段，用于跟踪配置模式变更。当示例版本高于本地 `config.yaml` 时，应用启动时会发出警告：

```
WARNING - Your config.yaml (version 0) is outdated — the latest version is 1.
Run `make config-upgrade` to merge new fields into your config.
```

- 配置中**缺少 `config_version`** 时，视为版本 0。
- 运行 `make config-upgrade` 可自动合并缺失字段（保留现有值，并创建 `.bak` 备份）。
- 修改配置模式时，请在 `config.example.yaml` 中递增 `config_version`。

## 配置章节

### 模型（Models）

配置智能体可用的 LLM 模型：

```yaml
models:
  - name: gpt-4                    # 内部标识符
    display_name: GPT-4            # 可读名称
    use: langchain_openai:ChatOpenAI  # LangChain 类路径
    model: gpt-4                   # API 使用的模型标识
    api_key: $OPENAI_API_KEY       # API 密钥（使用环境变量）
    max_tokens: 4096               # 单次请求最大 token 数
    temperature: 0.7               # 采样温度
```

**支持的提供商**：
- OpenAI（`langchain_openai:ChatOpenAI`）
- Anthropic（`langchain_anthropic:ChatAnthropic`）
- DeepSeek（`langchain_deepseek:ChatDeepSeek`）
- 小米 MiMo（`deerflow.models.patched_mimo:PatchedChatMiMo`）
- Claude Code OAuth（`deerflow.models.claude_provider:ClaudeChatModel`）
- Codex CLI（`deerflow.models.openai_codex_provider:CodexChatModel`）
- 任意 LangChain 兼容提供商

基于 CLI 的提供商示例：

```yaml
models:
  - name: gpt-5.4
    display_name: GPT-5.4 (Codex CLI)
    use: deerflow.models.openai_codex_provider:CodexChatModel
    model: gpt-5.4
    supports_thinking: true
    supports_reasoning_effort: true

  - name: claude-sonnet-4.6
    display_name: Claude Sonnet 4.6 (Claude Code OAuth)
    use: deerflow.models.claude_provider:ClaudeChatModel
    model: claude-sonnet-4-6
    max_tokens: 4096
    supports_thinking: true
```

**CLI 提供商的认证行为**：
- `CodexChatModel` 从 `~/.codex/auth.json` 加载 Codex CLI 认证信息
- Codex Responses 端点目前拒绝 `max_tokens` 和 `max_output_tokens`，因此 `CodexChatModel` 不暴露请求级 token 上限
- `ClaudeChatModel` 接受 `CLAUDE_CODE_OAUTH_TOKEN`、`ANTHROPIC_AUTH_TOKEN`、`CLAUDE_CODE_OAUTH_TOKEN_FILE_DESCRIPTOR`、`CLAUDE_CODE_CREDENTIALS_PATH`，或明文 `~/.claude/.credentials.json`
- 在 macOS 上，DeerFlow 不会自动探测 Keychain。需要时请使用 `scripts/export_claude_code_oauth.py` 显式导出 Claude Code 认证信息

若要通过 LangChain 使用 OpenAI 的 `/v1/responses` 端点，继续使用 `langchain_openai:ChatOpenAI` 并设置：

```yaml
models:
  - name: gpt-5-responses
    display_name: GPT-5 (Responses API)
    use: langchain_openai:ChatOpenAI
    model: gpt-5
    api_key: $OPENAI_API_KEY
    use_responses_api: true
    output_version: responses/v1
```

对于 OpenAI 兼容网关（例如 Novita 或 OpenRouter），继续使用 `langchain_openai:ChatOpenAI` 并设置 `base_url`：

```yaml
models:
  - name: novita-deepseek-v3.2
    display_name: Novita DeepSeek V3.2
    use: langchain_openai:ChatOpenAI
    model: deepseek/deepseek-v3.2
    api_key: $NOVITA_API_KEY
    base_url: https://api.novita.ai/openai
    supports_thinking: true
    when_thinking_enabled:
      extra_body:
        thinking:
          type: enabled

  - name: minimax-m3
    display_name: MiniMax M3
    use: langchain_openai:ChatOpenAI
    model: MiniMax-M3
    api_key: $MINIMAX_API_KEY
    base_url: https://api.minimax.io/v1
    max_tokens: 4096
    temperature: 1.0  # MiniMax 要求 temperature 在 (0.0, 1.0] 范围内
    supports_vision: true

  - name: minimax-m2.7
    display_name: MiniMax M2.7
    use: langchain_openai:ChatOpenAI
    model: MiniMax-M2.7
    api_key: $MINIMAX_API_KEY
    base_url: https://api.minimax.io/v1
    max_tokens: 4096
    temperature: 1.0  # MiniMax 要求 temperature 在 (0.0, 1.0] 范围内
    supports_vision: false  # M2.7 仅支持文本；M3 支持视觉

  - name: minimax-m2.7-highspeed
    display_name: MiniMax M2.7 Highspeed
    use: langchain_openai:ChatOpenAI
    model: MiniMax-M2.7-highspeed
    api_key: $MINIMAX_API_KEY
    base_url: https://api.minimax.io/v1
    max_tokens: 4096
    temperature: 1.0  # MiniMax 要求 temperature 在 (0.0, 1.0] 范围内
    supports_vision: false  # M2.7 仅支持文本；M3 支持视觉
  - name: openrouter-gemini-2.5-flash
    display_name: Gemini 2.5 Flash (OpenRouter)
    use: langchain_openai:ChatOpenAI
    model: google/gemini-2.5-flash-preview
    api_key: $OPENAI_API_KEY
    base_url: https://openrouter.ai/api/v1
```

若 OpenRouter 密钥使用不同的环境变量名，请显式指定 `api_key`（例如 `api_key: $OPENROUTER_API_KEY`）。

**思考模式（Thinking Models）**：
部分模型支持「思考」模式，用于复杂推理：

```yaml
models:
  - name: deepseek-v3
    supports_thinking: true
    when_thinking_enabled:
      extra_body:
        thinking:
          type: enabled
```

**通过 OpenAI 兼容网关使用带思考的 Gemini**：

当通过 OpenAI 兼容代理（Vertex AI OpenAI 兼容端点、AI Studio 或第三方网关）路由 Gemini 并启用思考模式时，API 会在响应中每个工具调用对象上附加 `thought_signature`。后续重放这些 assistant 消息的请求**必须**在工具调用条目上回传这些签名，否则 API 会返回：

```
HTTP 400 INVALID_ARGUMENT: function call `<tool>` in the N. content block is
missing a `thought_signature`.
```

标准 `langchain_openai:ChatOpenAI` 在序列化消息时会静默丢弃 `thought_signature`。请改用 `deerflow.models.patched_openai:PatchedChatOpenAI`——它会在每个出站请求中重新注入工具调用签名（来源为 `AIMessage.additional_kwargs["tool_calls"]`）：

```yaml
models:
  - name: gemini-2.5-pro-thinking
    display_name: Gemini 2.5 Pro (Thinking)
    use: deerflow.models.patched_openai:PatchedChatOpenAI
    model: google/gemini-2.5-pro-preview   # 网关期望的模型名称
    api_key: $GEMINI_API_KEY
    base_url: https://<your-openai-compat-gateway>/v1
    max_tokens: 16384
    supports_thinking: true
    supports_vision: true
    when_thinking_enabled:
      extra_body:
        thinking:
          type: enabled
```

若访问 Gemini **未启用**思考模式（例如通过 OpenRouter 且未激活思考），使用普通 `langchain_openai:ChatOpenAI` 并设置 `supports_thinking: false` 即可，无需补丁。

**通过 OpenAI 兼容 API 使用带思考的 MiMo**：

MiMo 在思考模式下会在 assistant 消息中返回 `reasoning_content`。在多轮智能体对话（含工具调用）中，后续请求必须保留历史 assistant 消息中的 `reasoning_content`，否则 MiMo API 可能返回 HTTP 400。标准 `langchain_openai:ChatOpenAI` 会丢弃该提供商特有字段，因此请使用 `deerflow.models.patched_mimo:PatchedChatMiMo`：

按量付费 API 密钥（`sk-...`）使用 `https://api.xiaomimimo.com/v1`。Token Plan 密钥（`tp-...`）使用 MiMo 控制台显示的区域 Token Plan Base URL，例如 `https://token-plan-cn.xiaomimimo.com/v1`。MiMo 文档说明这两种密钥类型相互独立、不可混用。

`PatchedChatMiMo` 与模型 ID 无关。配置的所有 MiMo 思考模型条目都应使用它，包括 `subagents.*.model` 覆盖引用的模型（例如 `mimo-v2.5-pro`、`mimo-v2.5`、`mimo-v2-pro`、`mimo-v2-omni` 或 `mimo-v2-flash`）。

```yaml
models:
  - name: mimo-v2.5-pro
    display_name: MiMo V2.5 Pro
    use: deerflow.models.patched_mimo:PatchedChatMiMo
    model: mimo-v2.5-pro
    api_key: $MIMO_API_KEY
    base_url: https://api.xiaomimimo.com/v1
    max_tokens: 8192
    supports_thinking: true
    supports_vision: false
    when_thinking_enabled:
      extra_body:
        thinking:
          type: enabled
    when_thinking_disabled:
      extra_body:
        thinking:
          type: disabled
```

`PatchedChatMiMo` 保留 MiMo 的 `choices[].message.reasoning_content`、流式 `delta.reasoning_content`，以及请求历史中 assistant 的 `reasoning_content` 字段。它不会复用 DeepSeek 提供商。

### 工具组（Tool Groups）

将工具组织为逻辑分组：

```yaml
tool_groups:
  - name: web          # 网页浏览与搜索
  - name: file:read    # 只读文件操作
  - name: file:write   # 写入文件操作
  - name: bash         # Shell 命令执行
```

### 工具（Tools）

配置智能体可用的具体工具：

```yaml
tools:
  - name: web_search
    group: web
    use: deerflow.community.tavily.tools:web_search_tool
    max_results: 5
    # api_key: $TAVILY_API_KEY  # 可选
```

**内置工具**：
- `web_search` — 网页搜索（DuckDuckGo、Tavily、Exa、InfoQuest、Firecrawl）
- `web_fetch` — 抓取网页（Jina AI、Exa、InfoQuest、Firecrawl）
- `ls` — 列出目录内容
- `read_file` — 读取文件内容
- `write_file` — 写入文件内容
- `str_replace` — 文件内字符串替换
- `bash` — 执行 bash 命令

### 沙箱（Sandbox）

DeerFlow 支持多种沙箱执行模式。在 `config.yaml` 中配置首选模式：

**本地执行**（在宿主机上直接运行沙箱代码）：
```yaml
sandbox:
   use: deerflow.sandbox.local:LocalSandboxProvider # 本地执行
   allow_host_bash: false # 默认关闭；除非显式重新启用，否则禁用宿主机 bash
```

**Docker 执行**（在隔离的 Docker 容器中运行沙箱代码）：
```yaml
sandbox:
   use: deerflow.community.aio_sandbox:AioSandboxProvider # 基于 Docker 的沙箱
```

**Docker + Kubernetes 执行**（通过 provisioner 服务在 Kubernetes Pod 中运行沙箱代码）：

此模式在**宿主机集群**上为每个沙箱运行独立的 Kubernetes Pod。需要 Docker Desktop K8s、OrbStack 或类似的本地 K8s 环境。

```yaml
sandbox:
   use: deerflow.community.aio_sandbox:AioSandboxProvider
   provisioner_url: http://provisioner:8002
```

使用 Docker 开发模式（`make docker-start`）时，仅当配置了 provisioner 模式时 DeerFlow 才会启动 `provisioner` 服务。在本地或普通 Docker 沙箱模式下会跳过 `provisioner`。

详细配置、前置条件与故障排除请参阅 [Provisioner 设置指南](../../docker/provisioner/README.md)。

在本地执行与基于 Docker 的隔离之间选择：

**方案 1：本地沙箱**（默认，配置更简单）：
```yaml
sandbox:
  use: deerflow.sandbox.local:LocalSandboxProvider
  allow_host_bash: false
```

`allow_host_bash` 默认有意设为 `false`。DeerFlow 的本地沙箱是宿主机侧的便利模式，而非安全的 Shell 隔离边界。若需要 `bash`，请优先使用 `AioSandboxProvider`。仅在完全可信的单用户本地工作流中才设置 `allow_host_bash: true`。

**方案 2：Docker 沙箱**（隔离性更好，更安全）：
```yaml
sandbox:
  use: deerflow.community.aio_sandbox:AioSandboxProvider
  port: 8080
  auto_start: true
  container_prefix: deer-flow-sandbox

  # 可选：额外挂载
  mounts:
    - host_path: /path/on/host
      container_path: /path/in/container
      read_only: false
```

配置 `sandbox.mounts` 后，DeerFlow 会在智能体提示中暴露这些 `container_path`，使智能体能够直接发现并操作挂载目录，而不必假定所有内容都在 `/mnt/user-data` 下。

对于使用 localhost 的裸机 Docker 沙箱运行，DeerFlow 默认将沙箱 HTTP 端口绑定到 `127.0.0.1`，避免暴露在所有宿主机网卡上。通过 `host.docker.internal` 连接的 Docker-outside-of-Docker 部署保留较宽的旧版绑定以保持兼容。若部署需要不同的绑定地址，请显式设置 `DEER_FLOW_SANDBOX_BIND_HOST`。

### 技能（Skills）

配置专用工作流所需的技能目录：

```yaml
skills:
  # 宿主机路径（可选，默认：../skills）
  path: /custom/path/to/skills

  # 容器内挂载路径（默认：/mnt/skills）
  container_path: /mnt/skills
```

**技能工作原理**：
- 技能存放在 `deer-flow/skills/{public,custom}/`
- 每个技能包含带元数据的 `SKILL.md` 文件
- 技能会自动发现并加载
- 本地与 Docker 沙箱均通过路径映射可用

**按智能体过滤技能**：
自定义智能体可在其 `config.yaml`（位于 `workspace/agents/<agent_name>/config.yaml`）中通过 `skills` 字段限制加载的技能：
- **省略或为 `null`**：加载所有全局启用的技能（默认回退行为）。
- **`[]`（空列表）**：为该智能体禁用所有技能。
- **`["skill-name"]`**：仅加载显式指定的技能。

### 标题生成（Title Generation）

自动生成对话标题：

```yaml
title:
  enabled: true
  max_words: 6
  max_chars: 60
  model_name: null  # 使用模型列表中的第一个模型
```

### GitHub API 令牌（GitHub Deep Research 技能可选）

默认 GitHub API 速率限制较为严格。若需频繁进行项目调研，建议配置具有只读权限的个人访问令牌（PAT）。

**配置步骤**：
1. 在 `.env` 文件中取消注释 `GITHUB_TOKEN` 行并填入个人访问令牌
2. 重启 DeerFlow 服务使更改生效

## 环境变量

DeerFlow 支持使用 `$` 前缀进行环境变量替换：

```yaml
models:
  - api_key: $OPENAI_API_KEY  # 从环境变量读取
```

**常用环境变量**：
- `OPENAI_API_KEY` — OpenAI API 密钥
- `ANTHROPIC_API_KEY` — Anthropic API 密钥
- `DEEPSEEK_API_KEY` — DeepSeek API 密钥
- `MIMO_API_KEY` — 小米 MiMo API 密钥
- `NOVITA_API_KEY` — Novita API 密钥（OpenAI 兼容端点）
- `TAVILY_API_KEY` — Tavily 搜索 API 密钥
- `DEER_FLOW_PROJECT_ROOT` — 相对运行时路径的项目根目录
- `DEER_FLOW_CONFIG_PATH` — 自定义配置文件路径
- `DEER_FLOW_EXTENSIONS_CONFIG_PATH` — 自定义扩展配置文件路径
- `DEER_FLOW_HOME` — 运行时状态目录（默认为项目根下的 `.deer-flow`）
- `DEER_FLOW_SKILLS_PATH` — 省略 `skills.path` 时使用的技能目录
- `GATEWAY_ENABLE_DOCS` — 设为 `false` 可禁用 Swagger UI（`/docs`）、ReDoc（`/redoc`）和 OpenAPI 模式（`/openapi.json`）端点（默认：`true`）

## 配置文件位置

配置文件应放在**项目根目录**（`deer-flow/config.yaml`）。若进程可能从其他工作目录启动，请设置 `DEER_FLOW_PROJECT_ROOT`；或设置 `DEER_FLOW_CONFIG_PATH` 指向具体文件。

## 配置查找优先级

DeerFlow 按以下顺序查找配置：

1. 代码中通过 `config_path` 参数指定的路径
2. `DEER_FLOW_CONFIG_PATH` 环境变量指定的路径
3. `DEER_FLOW_PROJECT_ROOT` 下的 `config.yaml`；未设置 `DEER_FLOW_PROJECT_ROOT` 时使用当前工作目录
4. 为兼容 monorepo 而保留的旧版 backend/仓库根目录位置

## 最佳实践

1. **将 `config.yaml` 放在项目根目录** — 若运行时从其他位置启动，请设置 `DEER_FLOW_PROJECT_ROOT`
2. **切勿提交 `config.yaml`** — 已在 `.gitignore` 中
3. **密钥使用环境变量** — 不要硬编码 API 密钥
4. **保持 `config.example.yaml` 更新** — 记录所有新增选项
5. **先在本地测试配置变更** — 再部署
6. **生产环境使用 Docker 沙箱** — 隔离性与安全性更好

## 故障排除

### 「找不到配置文件」
- 确认 `config.yaml` 存在于**项目根目录**（`deer-flow/config.yaml`）
- 若运行时从项目根外启动，请设置 `DEER_FLOW_PROJECT_ROOT`
- 或设置 `DEER_FLOW_CONFIG_PATH` 指向自定义位置

### 「API 密钥无效」
- 确认环境变量设置正确
- 确认环境变量引用使用了 `$` 前缀

### 「技能未加载」
- 确认 `deer-flow/skills/` 目录存在
- 确认技能包含有效的 `SKILL.md` 文件
- 若使用自定义路径，检查 `skills.path` 或 `DEER_FLOW_SKILLS_PATH`

### 「Docker 沙箱启动失败」
- 确认 Docker 正在运行
- 确认端口 8080（或配置的端口）可用
- 确认 Docker 镜像可访问

## 示例

完整配置选项示例请参阅 `config.example.yaml`。
