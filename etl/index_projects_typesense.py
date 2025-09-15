# opt/airflow/ext/etl/index_projects_typesense.py
"""
INDEX PROJECTS → Genera/actualiza embeddings en Supabase (pgvector) a partir de lake/gold
- Lee /lake/gold/dim_project.parquet (configurable por env PROJECTS_PARQUET o GOLD_DIR)
- Crea tabla project_search (si no existe) con vector(384) e índices IVFFlat/HNSW
- Calcula hash del texto; solo re-embeddea nuevos/cambiados
- Inserta/actualiza filas en Supabase
- Devuelve métricas (indexed, seconds, timestamp)
"""

import os
import time
from datetime import datetime, timezone
from typing import List, Dict, Any

import pandas as pd
import asyncio
import httpx

from api.services.typesense_client import get_admin_client

# =====================
# Config
# =====================
TYPESENSE_COLLECTION = os.getenv("TYPESENSE_COLLECTION", "project_search")
TS_VECTOR_DISTANCE = os.getenv("TS_VECTOR_DISTANCE", "cosine")  # cosine|l2|dotproduct
EMBED_DIMS = int(os.getenv("EMBED_DIMS", "384"))
EMBED_BATCH = int(os.getenv("EMBED_BATCH", "128"))

SUPABASE_EMBED_URL = os.getenv("SUPABASE_EMBED_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


# =====================
# Embeddings (Supabase Function)
# =====================
async def _embed_http(texts: List[str]) -> List[List[float]]:
    if not SUPABASE_EMBED_URL:
        raise RuntimeError("SUPABASE_EMBED_URL no configurada")

    headers = {"Content-Type": "application/json"}
    if SUPABASE_SERVICE_ROLE_KEY:
        headers["Authorization"] = f"Bearer {SUPABASE_SERVICE_ROLE_KEY}"

    payload = {"inputs": texts}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(SUPABASE_EMBED_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        # Soporta {"embeddings": [...]} o lista directa
        if isinstance(data, dict) and "embeddings" in data:
            return data["embeddings"]
        return data


def embed_batch_sync(texts: List[str]) -> List[List[float]]:
    return asyncio.run(_embed_http(texts))


# =====================
# Typesense: schema mínimo (PoC)
# =====================
def _ensure_collection(ts, dims: int):
    """
    Mínimo útil para PoC:
      - id, project_id, title, abstract, embedding
      - (Opcional) country/year como facet si querés filtrar (dejados activos)
    """
    schema_v026 = {
        "name": TYPESENSE_COLLECTION,
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "project_id", "type": "int64"},
            {"name": "title", "type": "string"},
            {"name": "abstract", "type": "string"},
            {"name": "country", "type": "string", "facet": True},
            {"name": "year", "type": "int32", "facet": True},
            {"name": "embedding", "type": "float[]"},
        ],
        "vectors": [
            {"name": "embedding", "size": dims, "distance": TS_VECTOR_DISTANCE}
        ],
    }
    try:
        ts.collections[TYPESENSE_COLLECTION].retrieve()
    except Exception:
        try:
            ts.collections.create(schema_v026)
        except Exception as e:
            # Fallback para Typesense 0.25 (solo un vector)
            if "unknown field: vectors" in str(e).lower():
                schema_v025 = dict(schema_v026)
                schema_v025["vector"] = {"size": dims, "distance": TS_VECTOR_DISTANCE}
                schema_v025.pop("vectors", None)
                ts.collections.create(schema_v025)
            else:
                raise


# =====================
# Fuente de datos (ajustá a tu realidad)
# =====================
def _fetch_projects_df() -> pd.DataFrame:
    """
    Reemplazá por tu loader real (Postgres/Parquet/CSV, etc.).
    Debe devolver columnas: project_id, title, abstract, country, year
    """
    # Placeholder vacío para que completes
    return pd.DataFrame([], columns=["project_id", "title", "abstract", "country", "year"])


# =====================
# Entrypoint
# =====================
def main() -> Dict[str, Any]:
    start = time.time()

    df = _fetch_projects_df()
    if df.empty:
        return {
            "indexed": 0,
            "seconds": round(time.time() - start, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    ts = get_admin_client()
    _ensure_collection(ts, EMBED_DIMS)

    docs: List[Dict[str, Any]] = []

    for i in range(0, len(df), EMBED_BATCH):
        chunk = df.iloc[i:i + EMBED_BATCH]
        texts = [f"{str(row.get('title') or '')} {str(row.get('abstract') or '')}".strip()
                 for _, row in chunk.iterrows()]
        vecs = embed_batch_sync(texts)

        for (idx, row), vec in zip(chunk.iterrows(), vecs):
            pid = row.get("project_id")
            if pd.isna(pid):
                continue
            pid = int(pid)
            title = str(row.get("title") or "")
            abstract = str(row.get("abstract") or "")

            doc = {
                "id": str(pid),
                "project_id": pid,
                "title": title,
                "abstract": abstract,
                "country": (str(row.get("country") or "") or None),
                "year": (int(row.get("year")) if pd.notna(row.get("year")) else None),
                "embedding": vec,
            }
            docs.append(doc)

    if docs:
        ts.collections[TYPESENSE_COLLECTION].documents().import_(
            docs, {"action": "upsert", "batch_size": 100}
        )

    return {
        "indexed": int(len(docs)),
        "seconds": round(time.time() - start, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    stats = main()
    print(stats)
