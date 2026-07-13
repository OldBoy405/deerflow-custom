# 记忆系统改进 - 摘要

## 同步说明（2026-03-10）

本摘要与 `main` 分支实现保持同步。
TF-IDF/上下文感知检索目前为**计划中**能力，尚未合并。

## 已实现

- 记忆注入中使用 `tiktoken` 进行精确 token 计数。
- Facts 会注入到 `<memory>` 提示词内容中。
- Facts 按置信度排序，并受 `max_injection_tokens` 限制。

## 计划中（尚未合并）

- 基于近期对话上下文的 TF-IDF 余弦相似度召回。
- 为 `format_memory_for_injection` 增加 `current_context` 参数。
- 加权排序（`similarity` + `confidence`）。
- 运行时提取/注入流程，用于上下文感知的事实筛选。

## 为何需要本次同步

早期文档将 TF-IDF 行为描述为已实现，与 `main` 分支代码不一致。
该差异由 Issue `#1059` 跟踪。

## 当前 API 形态

```python
def format_memory_for_injection(memory_data: dict[str, Any], max_tokens: int = 2000) -> str:
```

`main` 分支中目前**没有** `current_context` 参数。

## 验证指引

- 实现代码：`packages/harness/deerflow/agents/memory/prompt.py`
- 提示词组装：`packages/harness/deerflow/agents/lead_agent/prompt.py`
- 回归测试：`backend/tests/test_memory_prompt_injection.py`
