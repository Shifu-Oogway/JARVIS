from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_context_engine, get_graph, get_store, get_vault

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("")
async def overview(store=Depends(get_store)) -> dict:
    return {
        "counts": store.counts(),
        "recent": [
            {"id": r.id, "layer": r.layer, "preview": r.content[:120],
             "vault_path": r.vault_path}
            for r in store.recent(10)
        ],
    }


@router.post("/search")
async def search(body: dict, store=Depends(get_store)) -> list[dict]:
    query = body.get("query")
    if not query:
        raise HTTPException(422, "query is required")
    results = await store.search(query, k=body.get("k", 8))
    return [
        {"score": round(score, 4), "layer": r.layer,
         "title": r.meta.get("title"), "preview": r.content[:200],
         "vault_path": r.vault_path}
        for r, score in results
    ]


@router.post("/context")
async def context_preview(body: dict, engine=Depends(get_context_engine)) -> dict:
    objective = body.get("objective")
    if not objective:
        raise HTTPException(422, "objective is required")
    pkg = await engine.assemble(objective, active_context=body.get("active", ""))
    return {
        "token_estimate": pkg.token_estimate,
        "layers_used": pkg.layers_used,
        "sources": pkg.sources,
        "text": pkg.text,
    }


vault_router = APIRouter(tags=["memory"])


@vault_router.get("/vault/tree")
async def vault_tree(vault=Depends(get_vault)) -> dict:
    return vault.tree()


@vault_router.get("/graph")
async def graph(g=Depends(get_graph)) -> dict:
    return g.to_dict()
