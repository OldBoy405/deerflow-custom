# 待办清单

## 已完成功能

- [x] 仅在首次调用文件系统或 bash 工具后再启动 sandbox
- [x] 为全流程增加澄清（Clarification）机制
- [x] 实现上下文摘要机制，避免上下文膨胀
- [x] 集成 MCP（Model Context Protocol）以支持可扩展工具
- [x] 增加文件上传，并支持自动文档转换
- [x] 实现线程标题自动生成
- [x] 增加 Plan Mode 与 TodoList 中间件
- [x] 通过 ViewImageMiddleware 支持视觉模型
- [x] 基于 SKILL.md 格式的 Skills 系统
- [x] 在 `packages/harness/deerflow/tools/builtins/task_tool.py` 中将 `time.sleep(5)` 替换为 `asyncio.sleep()`（子代理轮询）

## 计划功能

- [ ] 对 sandbox 资源做池化，减少 sandbox 容器数量
- [ ] 增加认证/授权层
- [ ] 实现速率限制
- [ ] 增加指标与监控
- [ ] 上传支持更多文档格式
- [ ] Skill 市场 / 远程 Skill 安装
- [ ] 优化 Agent 热路径上的异步并发（IM 渠道多任务场景）
- [ ] 在 `packages/harness/deerflow/sandbox/local/local_sandbox.py` 中将 `subprocess.run()` 替换为 `asyncio.create_subprocess_shell()`
  - 在社区工具（tavily、jina_ai、firecrawl、infoquest、image_search）中将同步 `requests` 替换为 `httpx.AsyncClient`
  - [x] 在 title_middleware 与 memory updater 中将同步 `model.invoke()` 替换为异步 `model.ainvoke()`
  - 考虑对其余阻塞式文件 I/O 使用 `asyncio.to_thread()` 包装
  - 生产环境：针对长时间运行的 Agent 工作负载调优 Gateway worker/runtime 配置

## 已解决问题

- [x] 确保 `state.artifacts` 中不出现重复文件
- [x] 长时间思考但正文为空（答案藏在思考过程中）
