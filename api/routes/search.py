# search.py
from fastapi import APIRouter, HTTPException, Query
import os
import json
import httpx

router = APIRouter()

# --- Config desde variables de entorno ---
TS_HOST = os.getenv("TYPESENSE_HOST", "typesense")
TS_PORT = os.getenv("TYPESENSE_PORT", "8108")
TS_PROTO = os.getenv("TYPESENSE_PROTOCOL", "http")
TS_KEY = os.getenv("TYPESENSE_API_KEY")
TS_COLL = os.getenv("TYPESENSE_COLLECTION", "project_search")

SUPABASE_EMBED_URL = os.getenv("SUPABASE_EMBED_URL")
VERIFY_SSL = os.getenv("HTTPX_VERIFY", "1") != "0"  # poné HTTPX_VERIFY=0 para PoC sin cert


def _build_filter_by(country: str | None, year_min: int | None, year_max: int | None) -> str:
    parts: list[str] = []
    if country:
        parts.append(f"country:={country}")
    if year_min is not None:
        parts.append(f"year:>={year_min}")
    if year_max is not None:
        parts.append(f"year:<={year_max}")
    return " && ".join(parts)


def _format_hits_only(raw: dict) -> list[dict]:
    """
    Devuelve solo la lista de hits, con campos útiles + highlights (si los hay).
    """
    results = raw.get("results", [])
    hits = results[0].get("hits", []) if results else []

    def highlights_map(h: dict) -> dict:
        out = {}
        for hl in h.get("highlights", []):
            field = hl.get("field")
            snippet = hl.get("snippet")
            if field and snippet:
                out[field] = snippet
        return out

    out_hits: list[dict] = []
    for h in hits:
        doc = h.get("document", {})
        dist = h.get("vector_distance")
        sim = None
        if dist is not None:
            try:
                sim = round(1.0 - float(dist), 6)  # PoC simple
            except Exception:
                sim = None

        out_hits.append({
            "id": doc.get("id"),
            "project_id": doc.get("project_id"),
            "title": doc.get("title"),
            "abstract": doc.get("abstract"),
            "country": doc.get("country"),
            "year": doc.get("year"),
            "similarity": sim,
            "highlights": highlights_map(h),  # p.ej. { "title": "...", "abstract": "..." }
        })
    return out_hits


@router.get("/search/typesense")
async def search_typesense(
    q: str = Query(..., description="Consulta del usuario"),
    k: int = Query(5, ge=1, le=50, description="Cantidad de resultados"),
    # por defecto híbrido (texto + vector) así obtenés highlights útiles
    vector_only: bool = Query(False, description="True = vector puro; False = híbrido (BM25 + vector)"),
    country: str | None = Query(None, description="Filtro exacto por país, ej: AR"),
    year_min: int | None = Query(None, ge=0, description="Año mínimo (>=)"),
    year_max: int | None = Query(None, ge=0, description="Año máximo (<=)"),
):
    if not SUPABASE_EMBED_URL:
        raise HTTPException(status_code=500, detail="SUPABASE_EMBED_URL no configurada")

    # 1) Embedding del query (Supabase Function)
    try:
        async with httpx.AsyncClient(timeout=30.0, verify=VERIFY_SSL) as s:
            er = await s.post(SUPABASE_EMBED_URL, json={"inputs": [q]})
            er.raise_for_status()
            emb = (er.json().get("embeddings") or [])[0]
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error llamando a embed: {e}")

    # 2) Multi-search (v0.25.x) con highlights y sin devolver 'embedding'
    url = f"{TS_PROTO}://{TS_HOST}:{TS_PORT}/multi_search?collection={TS_COLL}"
    filter_by = _build_filter_by(country, year_min, year_max)

    search_obj: dict = {
        "q": "*" if vector_only else q,
        "query_by": "title,abstract",
        "per_page": k,
        "include_fields": "id,project_id,title,abstract,country,year",  # solo lo que necesitamos
        "exclude_fields": "embedding",
        "vector_query": f"embedding:({json.dumps(emb)}, k:{k})",
    }

    # highlights (tiene más sentido en híbrido; igual no molesta si vector_only=True)
    search_obj["highlight_full_fields"] = "title,abstract"
    search_obj["highlight_affix_num_tokens"] = 8
    search_obj["snippet_threshold"] = 30

    if filter_by:
        search_obj["filter_by"] = filter_by

    payload = {"searches": [search_obj]}
    headers = {"X-TYPESENSE-API-KEY": TS_KEY, "Content-Type": "application/json"}

    # 3) Ejecutar y devolver solo los hits formateados
    try:
        async with httpx.AsyncClient(timeout=15.0, verify=VERIFY_SSL) as s:
            r = await s.post(url, headers=headers, json=payload)
        if r.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Typesense 404 en {url}")
        r.raise_for_status()
        raw = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error en Typesense: {e}")

    return _format_hits_only(raw)
