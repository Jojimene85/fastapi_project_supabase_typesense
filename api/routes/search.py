# api/routes/search.py
"""
SEARCH: endpoints de búsqueda sobre el data warehouse.
- GET /search/typesense : busca documentos en Typesense (texto o vector si la colección tiene 'embedding').
- GET /search/pgvector  : busca en Supabase/Postgres usando pgvector para similitud semántica.
"""

from __future__ import annotations

import os
from typing import List, Optional, Any, Dict

import httpx
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from anyio import to_thread

# Reusar servicios centralizados
from api.services.db import get_async_engine  # async engine (Supabase PG)
from api.services.typesense_client import get_admin_client  # cliente Typesense (sync)

router = APIRouter(prefix="/search", tags=["search"])

# ---------- Config ----------
TYPESENSE_COLLECTION = os.getenv("TYPESENSE_COLLECTION", "projects")
SEARCH_TABLE = os.getenv("SEARCH_TABLE", "project_search")

# Embeddings (SOLO Supabase Edge Function)
SUPABASE_EMBED_URL = os.getenv("SUPABASE_EMBED_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")


# ---------- Modelos ----------
class Hit(BaseModel):
    id: str
    project_id: int
    title: str = ""
    abstract: str = ""
    country: Optional[str] = None
    year: Optional[int] = None
    text: Optional[str] = None
    score: Optional[float] = Field(None, description="Similarity / relevance score")
    source: str = Field(..., description="typesense | pgvector")


class SearchResponse(BaseModel):
    query: str
    k: int
    hits: List[Hit]


# ---------- Helpers ----------
async def _embed_query(texts: List[str]) -> List[List[float]]:
    if not SUPABASE_EMBED_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise HTTPException(
            503,
            "Embeddings no configurados. Definí SUPABASE_EMBED_URL y SUPABASE_SERVICE_ROLE_KEY",
        )
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            SUPABASE_EMBED_URL,
            headers={
                "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
                "Content-Type": "application/json",
            },
            json={"inputs": texts},
        )
    r.raise_for_status()
    data = r.json()
    # Edge function típica devuelve {"embeddings":[...]}
    if isinstance(data, dict) and "embeddings" in data:
        return data["embeddings"]
    if isinstance(data, list):  # por si devuelve directamente la lista
        return data
    raise HTTPException(500, f"Formato inesperado del embedder: {data}")


# =========================================================
#                  /search/typesense
# =========================================================
@router.get("/typesense", response_model=SearchResponse)
async def search_typesense(
    q: str = Query(..., description="Query de búsqueda"),
    k: int = Query(10, ge=1, le=200),
    country: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    use_vector: bool = Query(False, description="Activa similaridad si la colección tiene campo 'embedding'"),
):
    """
    Búsqueda en Typesense: por texto y, opcionalmente, por vector (si la colección TS tiene 'embedding').
    El cliente oficial es sincrónico → lo corremos en thread para no bloquear el loop.
    """
    ts = get_admin_client()

    def _filters() -> Optional[str]:
        parts = []
        if country:
            parts.append(f"country:={country}")
        if year is not None:
            parts.append(f"year:={year}")
        return " && ".join(parts) if parts else None

    if use_vector:
        [vec] = await _embed_query([q])

        def _do_search_vec() -> Dict[str, Any]:
            params: Dict[str, Any] = {
                "q": q,
                "query_by": "title,abstract,text",
                "per_page": k,
                "vector_query": f"embedding:=[{','.join(map(str, vec))}]",
            }
            fb = _filters()
            if fb:
                params["filter_by"] = fb
            return ts.collections[TYPESENSE_COLLECTION].documents.search(params)

        raw = await to_thread.run_sync(_do_search_vec)

    else:
        def _do_search_text() -> Dict[str, Any]:
            params: Dict[str, Any] = {
                "q": q,
                "query_by": "title,abstract,text",
                "per_page": k,
            }
            fb = _filters()
            if fb:
                params["filter_by"] = fb
            return ts.collections[TYPESENSE_COLLECTION].documents.search(params)

        raw = await to_thread.run_sync(_do_search_text)

    hits: List[Hit] = []
    for item in raw.get("hits", []):
        doc = item.get("document", {})
        score = item.get("text_match") or item.get("vector_distance")
        hits.append(Hit(
            id=str(doc.get("id")),
            project_id=int(doc.get("project_id", 0)),
            title=doc.get("title", "") or "",
            abstract=doc.get("abstract", "") or "",
            country=doc.get("country"),
            year=doc.get("year"),
            text=doc.get("text"),
            score=float(score) if score is not None else None,
            source="typesense",
        ))

    return SearchResponse(query=q, k=k, hits=hits)


# =========================================================
#                  /search/pgvector
# =========================================================
@router.get("/pgvector", response_model=SearchResponse)
async def search_pgvector(
    q: str = Query(...),
    k: int = Query(10, ge=1, le=200),
    country: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """
    Búsqueda semántica en Supabase/Postgres usando pgvector:
      SELECT ... ORDER BY embedding <-> :qvec LIMIT :k
    Reusa el AsyncEngine de db.py.
    """
    [vec] = await _embed_query([q])
    vec_sql = f"[{','.join(map(str, vec))}]"

    filters = []
    if country:
        filters.append("country = :country")
    if year is not None:
        filters.append("year = :year")
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    sql = f"""
        SELECT project_id, title, abstract, country, year
        FROM {SEARCH_TABLE}
        {where}
        ORDER BY embedding <-> :qvec
        LIMIT :k
    """

    engine = get_async_engine()
    async with engine.connect() as conn:
        res = await conn.execute(
            text(sql),
            {"qvec": vec_sql, "k": k, "country": country, "year": year},
        )
        rows = [dict(r._mapping) for r in res.fetchall()]

    hits = [
        Hit(
            id=str(r["project_id"]),
            project_id=int(r["project_id"]),
            title=r.get("title") or "",
            abstract=r.get("abstract") or "",
            country=r.get("country"),
            year=r.get("year"),
            text=None,
            score=None,  # si querés score: SELECT (1 - (embedding <-> :qvec)) AS score
            source="pgvector",
        )
        for r in rows
    ]
    return SearchResponse(query=q, k=k, hits=hits)
