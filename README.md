# JARVIS — Enterprise AI Operating System

JARVIS is an AI command center and agent-orchestration platform: a Jarvis Core executive layer
that decomposes requests, routes them across multiple AI agents running on NVIDIA NIM, manages
layered memory backed by an Obsidian vault, and runs autonomous + scheduled workflows.

This repository is delivered in **executable phases**. Each phase compiles and runs before the next.

## Shipped so far

**Phase 2 — Memory & Obsidian** adds: the Obsidian vault adapter (markdown + frontmatter,
link/tag extraction), a knowledge graph, NeMo Retriever embeddings + reranker, the 4-layer rolling
context-assembly engine, and Raw→Summary→Knowledge→Vault compression — all wired into Jarvis Core.
New endpoints: `/memory`, `/memory/search`, `/memory/context`, `/vault/tree`, `/graph`.

## Phase 1 — Foundation

A runnable backbone that the remaining subsystems plug into:

- **Clean-architecture FastAPI backend** (`backend/app`) — domain / application / infrastructure / api layers.
- **NVIDIA NIM integration layer** — async OpenAI-compatible client, model capability registry,
  role-based router with round-robin load balancing + failover, and background health checks.
- **Agent framework** — `BaseAgent` with state, memory, a tool registry, metrics, and permissions,
  plus a concrete `ResearchAgent` and an agent registry.
- **Jarvis Core** — the executive layer: intent → task decomposition → agent assignment → synthesis.
- **Persistence** — SQLAlchemy 2.0 (async) models for agents, tasks, workflows, memory, schedules,
  backups, and audit logs, with Alembic wired up.
- **Event backbone** — Redis pub/sub event bus and a WebSocket event feed.
- **Observability hooks** — Prometheus `/metrics`, structured JSON logging.
- **Infra** — Docker Compose (Postgres, Redis, backend, frontend, Prometheus, Grafana).
- **Dashboard shell** — Next.js 15 command-center skeleton with live panels.

Later phases flesh out: voice (STT/TTS), Obsidian bi-directional sync + knowledge graph,
the rolling context-window engine, DAG workflow engine, scheduler, backup/restore, self-update,
RBAC/OAuth2, and the full dashboard. See `docs/ARCHITECTURE.md` for the roadmap.

## Quick start (Docker)

```bash
cp .env.example .env          # then set JARVIS_NIM_API_KEY
docker compose up --build
```

- API:        http://localhost:8000  (docs at /docs)
- Dashboard:  http://localhost:3000
- Prometheus: http://localhost:9090
- Grafana:    http://localhost:3001  (admin / admin)

## Local backend dev (no Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
```

The backend runs without a live NIM endpoint: the router degrades gracefully and Jarvis Core
falls back to a heuristic planner so you can exercise the full request path offline.
