# 记忆设置评审指南

在本地以最少手动步骤评审「记忆设置」的新增/编辑流程时，可参考本文档。

## 快速评审

1. 使用你已有的任意可用开发环境，在本地启动 DeerFlow。

   示例：

   ```bash
   make dev
   ```

   或

   ```bash
   make docker-start
   ```

   若本地已有运行中的 DeerFlow 实例，可直接复用。

2. 加载示例记忆 fixture。

   ```bash
   python scripts/load_memory_sample.py
   ```

3. 打开 `Settings > Memory`（设置 > 记忆）。

   默认本地地址：
   - 应用（经 nginx）：`http://localhost:2026`
   - 仅前端直连回退：`http://localhost:3000`

## 最小手动测试

1. 点击 `Add fact`（添加事实）。
2. 新建一条事实，填写：
   - Content（内容）：`Reviewer-added memory fact`
   - Category（类别）：`testing`
   - Confidence（置信度）：`0.88`
3. 确认新事实立即出现，且来源显示为 `Manual`。
4. 编辑示例事实 `This sample fact is intended for edit testing.`，修改为：
   - Content：`This sample fact was edited during manual review.`
   - Category：`testing`
   - Confidence：`0.91`
5. 确认编辑后事实立即更新。
6. 刷新页面，确认新增与编辑后的事实均已持久化。

## 可选健全性检查

- 搜索 `Reviewer-added`，确认能匹配到新事实。
- 搜索 `workflow`，确认类别文本可被检索。
- 在 `All`、`Facts`、`Summaries` 之间切换视图。
- 删除可丢弃的示例事实 `Delete fact testing can target this disposable sample entry.`，确认列表立即更新。
- 清空全部记忆，确认页面进入空状态。

## Fixture 文件

- 示例 fixture：`backend/docs/memory-settings-sample.json`
- 默认本地运行时目标文件：`backend/.deer-flow/memory.json`

加载脚本在覆盖已有运行时记忆文件前，会自动创建带时间戳的备份。
