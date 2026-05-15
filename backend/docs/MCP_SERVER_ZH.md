# MCP（Model Context Protocol，模型上下文协议）配置

DeerFlow 支持可配置的 MCP 服务器与技能以扩展能力，相关配置从项目根目录下的 `extensions_config.json` 加载。

## 设置

1. 将 `extensions_config.example.json` 复制为项目根目录下的 `extensions_config.json`。
   ```bash
   # 复制示例配置
   cp extensions_config.example.json extensions_config.json
   ```
2. 将需要启用的 MCP 服务器或技能对应项设为 `"enabled": true`。
3. 按需配置各服务器的命令、参数以及环境变量。
4. 重启应用以加载并注册 MCP 工具。

## OAuth 支持（HTTP/SSE MCP 服务器）

对于 `http` 与 `sse` 类型的 MCP 服务器，DeerFlow 支持获取 OAuth 访问令牌并自动刷新。

- 支持的授权类型：`client_credentials`、`refresh_token`
- 在 `extensions_config.json` 中为每个服务器配置 `oauth` 块
- 敏感信息应通过环境变量提供（例如：`$MCP_OAUTH_CLIENT_SECRET`）

示例：

```json
{
   "mcpServers": {
      "secure-http-server": {
         "enabled": true,
         "type": "http",
         "url": "https://api.example.com/mcp",
         "oauth": {
            "enabled": true,
            "token_url": "https://auth.example.com/oauth/token",
            "grant_type": "client_credentials",
            "client_id": "$MCP_OAUTH_CLIENT_ID",
            "client_secret": "$MCP_OAUTH_CLIENT_SECRET",
            "scope": "mcp.read",
            "refresh_skew_seconds": 60
         }
      }
   }
}
```

## 自定义工具拦截器

可以注册在每次调用 MCP 工具之前运行的自定义拦截器。适用于注入按请求区分的请求头（例如来自 LangGraph 执行上下文的用户认证令牌）、记录日志或采集指标等场景。

在 `extensions_config.json` 中通过 `mcpInterceptors` 字段声明拦截器：

```json
{
  "mcpInterceptors": [
    "my_package.mcp.auth:build_auth_interceptor"
  ],
  "mcpServers": { ... }
}
```

每一项为 `module:variable` 格式的 Python 导入路径（通过 `resolve_variable` 解析）。该变量必须是一个**无参构建函数**，返回与 `MultiServerMCPClient` 的 `tool_interceptors` 接口兼容的异步拦截器；若返回 `None` 则跳过。

以下示例从 LangGraph 的 metadata 注入认证头：

```python
def build_auth_interceptor():
    async def interceptor(request, handler):
        from langgraph.config import get_config
        metadata = get_config().get("metadata", {})
        headers = dict(request.headers or {})
        if token := metadata.get("auth_token"):
            headers["X-Auth-Token"] = token
        return await handler(request.override(headers=headers))
    return interceptor
```

- 允许使用单个字符串，系统会规范化为只含一个元素的列表。
- 路径无效或构建失败会记录为警告，且不会阻止其他拦截器。
- 构建函数的返回值必须是**可调用对象**；非可调用值会跳过并记录警告。

## 工作原理

MCP 服务器对外提供工具，这些工具会在运行时被自动发现并集成到 DeerFlow 的智能体系统中。启用后，智能体即可使用这些工具，通常无需再改业务代码。

## 能力示例

MCP 服务器可用于：

- **文件系统**
- **数据库**（例如 PostgreSQL）
- **外部 API**（例如 GitHub、Brave Search）
- **浏览器自动化**（例如 Puppeteer）
- **自定义 MCP 服务器实现**

## 延伸阅读

关于 Model Context Protocol 的详细说明，请参阅：  
https://modelcontextprotocol.io
