# JARVIS — Architecture & Phase Roadmap

## Layered architecture (clean architecture)

```
Frontend (Next.js command center)
        │  REST + WebSocket
API Gateway (FastAPI routers, CORS, metrics middleware)
        │
Jarvis Core  ── executive layer: intent → decompose → assign → coordinate → synthesise
        │
Agent Orchestrator (AgentRegistry; parallel dependency-aware dispatch)
        │
Agent Runtime (BaseAgent: state · memory · tools · metrics · permissions)
        │
NVIDIA NIM Layer (Router → HealthMonitor → NIMClient pool; ModelRegistry by role)
        │
Memory Layer (DB-backed entries + Obsidian vault + rolling context engine*)
        │
Storage Layer (PostgreSQL · Redis · vault filesystem)
```
`*` = Phase 2. Each layer depends only on the layer below via an interface, so any
layer is independently replaceable (e.g. swap NIM for vLLM by reimplementing the NIM client).

## Request lifecycle

1. Client → `POST /chat` → `JarvisCore.handle`.
2. `decompose` asks the **planning** model for a JSON task list (heuristic fallback offline).
3. `execute` runs each dependency-ready wave **in parallel** (`asyncio.gather`), feeding prior
   results forward as context.
4. `synthesize` merges agent outputs via the **executive** model.
5. Every step emits an event on the Redis bus → `GET /ws/events` → dashboard Event Feed.

## Event architecture

Single Redis pub/sub channel `jarvis.events`. Event shape: `{ kind, payload, ts }`.
Kinds emitted today: `request.received/completed`, `task.started/succeeded/failed`,
`agent.started/succeeded/failed`, `nim_health_change`. Telemetry never blocks a request —
publish failures are swallowed and logged.

## Database schema (Phase 1)

| table            | purpose                                            |
|------------------|----------------------------------------------------|
| `agents`         | persisted agent state, model binding, metrics      |
| `workflows`      | a decomposed request                               |
| `tasks`          | tasks within a workflow (FK → workflows), w/ result|
| `memory_entries` | layered memory (active/working/long_term/archive)  |
| `scheduled_jobs` | cron-driven directives                             |
| `backups`        | backup catalogue (full/incremental)                |
| `audit_logs`     | who did what                                       |

## NIM routing

`ModelRegistry` maps each `AgentRole` → `ModelSpec(name, context_window, max_concurrency, capabilities)`.
`NIMRouter` keeps a pool of `NIMClient`s (one per endpoint URL), round-robins across the
**healthy** subset, and fails over on error by demoting the endpoint. `HealthMonitor` re-probes
every 30s. Everything is config-driven via `JARVIS_NIM_BASE_URL` + `JARVIS_NIM_EXTRA_ENDPOINTS`.

## Phase roadmap

- **Phase 1 — Foundation (shipped):** clean-arch backend, NIM layer, agent framework,
  Jarvis Core, DB models + Alembic, event bus + WS feed, metrics, Docker infra, dashboard shell.
- **Phase 2 — Memory & Context:** rolling 4-layer context engine (active/working/long-term/archive),
  context-assembly + relevance ranking, Obsidian bi-directional sync, knowledge graph, compression.
- **Phase 3 — Workflow engine:** explicit DAG with retries, timeouts, checkpointing,
  dead-letter queue, conditional + dynamic (agent-spawning) graphs, visual graph in dashboard.
- **Phase 4 — Scheduler & autonomy:** cron/recurring/one-time/event-driven jobs; autonomous
  multi-step plans surfaced live.
- **Phase 5 — Voice:** full-duplex STT (streaming + wake word) and TTS (streaming, interruptible).
- **Phase 6 — Ops:** backup/restore (tar.gz, full/incremental, local/NAS/S3/SSH), self-update with
  signature verification + migrations + rollback, Maintenance Agent.
- **Phase 7 — Security & deploy:** RBAC, OAuth2/JWT, API keys, audit, secrets, TLS;
  Grafana/Loki dashboards; Kubernetes manifests (GPU nodes, HA, HPA); CI/CD.
