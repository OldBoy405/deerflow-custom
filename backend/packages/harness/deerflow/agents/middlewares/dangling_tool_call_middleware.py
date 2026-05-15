"""Middleware to fix dangling tool calls in message history.

A dangling tool call occurs when an AIMessage contains tool_calls but there are
no corresponding ToolMessages in the history (e.g., due to user interruption or
request cancellation). This causes LLM errors due to incomplete message format.

This middleware intercepts the model call to detect and patch such gaps by
inserting synthetic ToolMessages with an error indicator immediately after the
AIMessage that made the tool calls, ensuring correct message ordering.

Note: Uses wrap_model_call instead of before_model to ensure patches are inserted
at the correct positions (immediately after each dangling AIMessage), not appended
to the end of the message list as before_model + add_messages reducer would do.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, ToolMessage

logger = logging.getLogger(__name__)

_PLACEHOLDER = "[Tool call was interrupted and did not return a result.]"


def _tool_call_id_str(tc_id: object) -> str | None:
    if tc_id is None:
        return None
    return str(tc_id)


def repair_openai_compatible_tool_sequences(
    messages: list,
    *,
    message_tool_calls_fn,
) -> tuple[list, bool]:
    """Rebuild history so every AIMessage with tool_calls is immediately followed by
    one ToolMessage per tool_call_id (OpenAI / DeepSeek contract).

    Handles:
    - Missing tool results (synthetic placeholder)
    - **Out-of-order** tool results (e.g. another assistant/human inserted before tools)
    - tool_call_id type mismatches (str vs int) via normalization

    ToolMessage instances are consumed in AI tool_calls order; unconsumed tool
    messages are dropped with a warning (would be invalid if re-appended).
    """
    if not messages:
        return messages, False

    tool_by_id: dict[str, ToolMessage] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tid = _tool_call_id_str(msg.tool_call_id)
            if tid:
                tool_by_id[tid] = msg

    out: list = []
    consumed_tool_ids: set[str] = set()

    for msg in messages:
        if isinstance(msg, ToolMessage):
            # Emitted when we process the parent AIMessage; skip original position.
            continue
        if not isinstance(msg, AIMessage):
            out.append(msg)
            continue

        tcs = message_tool_calls_fn(msg)
        out.append(msg)
        if not tcs:
            continue

        for tc in tcs:
            tid = _tool_call_id_str(tc.get("id"))
            if not tid:
                continue
            if tid in consumed_tool_ids:
                continue
            existing = tool_by_id.get(tid)
            if existing is not None:
                out.append(existing)
                consumed_tool_ids.add(tid)
            else:
                out.append(
                    ToolMessage(
                        content=_PLACEHOLDER,
                        tool_call_id=tid,
                        name=tc.get("name", "unknown"),
                        status="error",
                    )
                )
                consumed_tool_ids.add(tid)

    for tid in tool_by_id:
        if tid not in consumed_tool_ids:
            logger.warning(
                "Dropping orphan ToolMessage (tool_call_id=%s) after repair — no matching AIMessage.tool_calls",
                tid,
            )

    same = len(out) == len(messages) and all(
        x is y for x, y in zip(out, messages, strict=True)
    )
    if same:
        return messages, False

    synthetic_count = sum(
        1
        for m in out
        if isinstance(m, ToolMessage) and m.content == _PLACEHOLDER and getattr(m, "status", None) == "error"
    )
    if synthetic_count:
        logger.warning("Injected %s synthetic ToolMessage(s) for missing tool results", synthetic_count)

    return out, True


class DanglingToolCallMiddleware(AgentMiddleware[AgentState]):
    """Inserts placeholder ToolMessages for dangling tool calls before model invocation.

    Scans the message history for AIMessages whose tool_calls lack corresponding
    ToolMessages, and injects synthetic error responses immediately after the
    offending AIMessage so the LLM receives a well-formed conversation.
    """

    @staticmethod
    def _message_tool_calls(msg) -> list[dict]:
        """Return normalized tool calls from structured fields or raw provider payloads.

        LangChain stores malformed provider function calls in ``invalid_tool_calls``.
        They do not execute, but provider adapters may still serialize enough of
        the call id/name back into the next request that strict OpenAI-compatible
        validators expect a matching ToolMessage. Treat them as dangling calls so
        the next model request stays well-formed and the model sees a recoverable
        tool error instead of another provider 400.
        """
        normalized: list[dict] = []

        tool_calls = getattr(msg, "tool_calls", None) or []
        normalized.extend(list(tool_calls))

        raw_tool_calls = (getattr(msg, "additional_kwargs", None) or {}).get("tool_calls") or []
        if not tool_calls:
            for raw_tc in raw_tool_calls:
                if not isinstance(raw_tc, dict):
                    continue

                function = raw_tc.get("function")
                name = raw_tc.get("name")
                if not name and isinstance(function, dict):
                    name = function.get("name")

                args = raw_tc.get("args", {})
                if not args and isinstance(function, dict):
                    raw_args = function.get("arguments")
                    if isinstance(raw_args, str):
                        try:
                            parsed_args = json.loads(raw_args)
                        except (TypeError, ValueError, json.JSONDecodeError):
                            parsed_args = {}
                        args = parsed_args if isinstance(parsed_args, dict) else {}

                normalized.append(
                    {
                        "id": raw_tc.get("id"),
                        "name": name or "unknown",
                        "args": args if isinstance(args, dict) else {},
                    }
                )

        for invalid_tc in getattr(msg, "invalid_tool_calls", None) or []:
            if not isinstance(invalid_tc, dict):
                continue
            normalized.append(
                {
                    "id": invalid_tc.get("id"),
                    "name": invalid_tc.get("name") or "unknown",
                    "args": {},
                    "invalid": True,
                    "error": invalid_tc.get("error"),
                }
            )

        return normalized

    @staticmethod
    def _synthetic_tool_message_content(tool_call: dict) -> str:
        if tool_call.get("invalid"):
            error = tool_call.get("error")
            if isinstance(error, str) and error:
                return f"[Tool call could not be executed because its arguments were invalid: {error}]"
            return "[Tool call could not be executed because its arguments were invalid.]"
        return "[Tool call was interrupted and did not return a result.]"

    def _build_patched_messages(self, messages: list) -> list | None:
        """Return repaired messages for OpenAI-compatible tool protocol, or None if unchanged."""
        repaired, changed = repair_openai_compatible_tool_sequences(
            messages,
            message_tool_calls_fn=self._message_tool_calls,
        )
        if not changed:
            return None

        return repaired

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        patched = self._build_patched_messages(request.messages)
        if patched is not None:
            request = request.override(messages=patched)
        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        patched = self._build_patched_messages(request.messages)
        if patched is not None:
            request = request.override(messages=patched)
        return await handler(request)
