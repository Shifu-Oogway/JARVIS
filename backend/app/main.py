"""JARVIS backend entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.metrics import MetricsMiddleware, metrics_app

from app.agents.registry import AgentRegistry
from app.api.router import api_router
from app.core.config import get_settings
from app.core.events import event_bus
from app.core.logging import configure_logging, get_logger
from app.core_engine.jarvis_core import JarvisCore
from app.infrastructure.obsidian.graph import KnowledgeGraph
from app.infrastructure.obsidian.vault import ObsidianVault
from app.memory.compression import MemoryCompressor
from app.memory.context_engine import ContextAssemblyEngine
from app.memory.embeddings import get_embedding_provider
from app.memory.reranker import Reranker
from app.memory.store import MemoryStore
from app.infrastructure.db.session import init_models
from app.infrastructure.nim.router import NIMRouter

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    log.info("jarvis_boot", environment=settings.environment)

    await event_bus.connect()
    nim_router = NIMRouter()
    await nim_router.start()
    agents = AgentRegistry(nim_router)

    # --- Memory & Obsidian subsystem (Phase 2) ---
    vault = ObsidianVault(settings.obsidian_vault_path)
    try:
        vault.ensure_structure()
    except OSError as exc:
        log.warning("vault_unavailable", error=str(exc))
    embedder = get_embedding_provider()
    store = MemoryStore(embedder)
    try:
        n = await store.hydrate_from_vault(vault)
        log.info("memory_hydrated", notes=n)
    except Exception as exc:  # noqa: BLE001
        log.warning("memory_hydrate_failed", error=str(exc))
    reranker = Reranker()
    graph = KnowledgeGraph.build(vault) if vault.root.exists() else KnowledgeGraph()
    context_engine = ContextAssemblyEngine(
        store, reranker, vault, graph, token_budget=settings.context_token_budget)
    compressor = MemoryCompressor(nim_router, vault, store)
    core = JarvisCore(nim_router, agents, context_engine=context_engine, compressor=compressor)

    app.state.nim_router = nim_router
    app.state.agents = agents
    app.state.core = core
    app.state.vault = vault
    app.state.memory_store = store
    app.state.context_engine = context_engine
    app.state.knowledge_graph = graph

    try:
        await init_models()
    except Exception as exc:  # noqa: BLE001 - boot without DB in pure-dev/offline runs
        log.warning("db_init_skipped", error=str(exc))

    yield

    await nim_router.stop()
    await event_bus.close()
    log.info("jarvis_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="JARVIS", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(MetricsMiddleware)
    app.include_router(api_router)
    app.mount("/metrics", metrics_app)
    return app


app = create_app()
