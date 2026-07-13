# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Summary

DeerFlow is an open-source super agent harness — Python 3.12 backend (LangGraph + FastAPI) with a Next.js 16 frontend. It orchestrates sub-agents, memory, sandboxes, and skills. Built by ByteDance.

Detailed architecture docs: [backend/CLAUDE.md](backend/CLAUDE.md) and [frontend/CLAUDE.md](frontend/CLAUDE.md).

## Commands

### Root (full application)

```bash
make check       # Verify prerequisites (Node 22+, pnpm, uv, nginx)
make install     # Install backend + frontend deps + pre-commit hooks
make dev         # Start all services with hot-reload → http://localhost:2026
make stop        # Stop all services
make config      # Generate config.yaml from template (first-time only; aborts if exists)
make setup       # Interactive setup wizard (recommended for new users)
```

`make dev` starts Gateway (8001), Frontend (3000), LangGraph API, and nginx (2026). Nginx routes `/api/langgraph/*` to the embedded LangGraph runtime and all other `/api/*` to Gateway REST APIs.

### Backend (`cd backend/`)

```bash
make lint        # ruff check + format check
make test        # Run all tests (277+ tests)
make format      # Auto-format with ruff
make dev         # Gateway API with reload on port 8001
```

Run a single test file: `PYTHONPATH=. uv run pytest tests/test_<name>.py -v`

### Frontend (`cd frontend/`)

```bash
pnpm lint        # ESLint
pnpm typecheck   # tsc --noEmit
pnpm build       # Production build (needs BETTER_AUTH_SECRET set)
pnpm dev         # Dev server with Turbopack on port 3000
pnpm test        # Vitest unit tests
```

## Architecture

### Service Topology

```
Browser → nginx (:2026) → /api/langgraph/* → Gateway embedded LangGraph runtime
                         → /api/*           → Gateway REST API (:8001)
                         → /*               → Frontend (:3000)
```

The Gateway API on port 8001 serves both REST endpoints and runs the LangGraph agent runtime in-process. There is no separate LangGraph server — `RunManager` + `run_agent()` + `StreamBridge` live inside the Gateway.

### Harness / App Split (Backend)

The backend enforces a strict dependency direction:

- **Harness** (`backend/packages/harness/deerflow/`) — Publishable agent framework with agent orchestration, tools, sandbox, models, MCP, skills, config. Import prefix: `deerflow.*`.
- **App** (`backend/app/`) — FastAPI Gateway API and IM channel integrations (Feishu, Slack, Telegram, DingTalk, WeChat, WeCom). Import prefix: `app.*`.

**Rule**: App imports deerflow, but deerflow never imports app. Enforced by `tests/test_harness_boundary.py`.

### Agent Middleware Chain

The lead agent (`deerflow.agents:make_lead_agent`) assembles 18 middleware components in order. Key ones:

| Order | Middleware | Purpose |
|-------|-----------|---------|
| 1 | ThreadDataMiddleware | Per-thread isolated directories |
| 3 | SandboxMiddleware | Acquires sandbox, stores sandbox_id |
| 6 | GuardrailMiddleware | Pre-tool-call authorization (optional) |
| 7 | SandboxAuditMiddleware | Security logging for shell/file ops |
| 9 | SummarizationMiddleware | Context reduction near token limits |
| 13 | MemoryMiddleware | Queues conversations for async memory updates |
| 17 | LoopDetectionMiddleware | Detects repeated tool-call loops |
| 18 | ClarificationMiddleware | Intercepts ask_clarification calls (must be last) |

### Sandbox

Abstract `Sandbox` interface with virtual path mapping:
- Agent sees `/mnt/user-data/{workspace,uploads,outputs}`, `/mnt/skills`
- Physical paths under `backend/.deer-flow/users/{user_id}/threads/{thread_id}/`
- Providers: `LocalSandboxProvider` (filesystem only, bash disabled by default) or `AioSandboxProvider` (Docker containers)

### Sub-Agent System

Lead agent spawns sub-agents via the `task()` tool. Max 3 concurrent, 15-min timeout. Built-in types: `general-purpose`, `bash`. Sub-agents run in isolated contexts with scoped tools.

### Config System

`config.yaml` (root) — models, tools, sandbox, memory, channels. Values starting with `$` resolve as env vars. Config is cached but auto-reloads on file change.

`extensions_config.json` (root) — MCP servers and skills. Hot-reloadable via Gateway API.

Configuration discovery order: explicit path arg → env var → `backend/` → project root (recommended).

## Gotchas

- `make config` is intentionally non-idempotent — it aborts if `config.yaml` already exists. Use `make config-upgrade` to merge new fields.
- Frontend `pnpm build` requires `BETTER_AUTH_SECRET` to be set. Workaround: `SKIP_ENV_VALIDATION=1`.
- `pnpm check` is unreliable — run `pnpm lint` and `pnpm typecheck` separately.
- Proxy env vars (`HTTP_PROXY`, etc.) can silently break `pnpm install`. Unset them if you get registry errors.
- On Windows, run local dev from Git Bash. cmd.exe and PowerShell are not supported for the bash service scripts.
- Docker Compose IM channels need `langgraph_url: http://gateway:8001/api` (container service name), not `localhost`.
- CI enforces backend lint + tests on every PR. Run `cd backend && make lint && make test` before pushing.
