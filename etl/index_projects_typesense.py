# opt/airflow/ext/etl/index_projects_typesense.py
"""
INDEX PROJECTS → Genera/actualiza embeddings en Supabase (pgvector) a partir de lake/gold
- Lee /lake/gold/dim_project.parquet (configurable por env PROJECTS_PARQUET o GOLD_DIR)
- Crea tabla project_search (si no existe) con vector(384) e índices IVFFlat/HNSW
- Calcula hash del texto; solo re-embeddea nuevos/cambiados
- Inserta/actualiza filas en Supabase
- Devuelve métricas (indexed, seconds, timestamp)
"""

from __future__ import annotations

import os
import time
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple

import httpx
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Reusar engine sync desde tus servicios
from api.services.db import get_engine  # Engine síncrono para ETL

# ---------- Config lectura ----------
GOLD_DIR = os.getenv("GOLD_DIR", "/lake/gold")
PROJECTS_PARQUET = os.getenv("PROJECTS_PARQUET", os.path.join(GOLD_DIR, "dim_project.parquet"))
SEARCH_TABLE = os.getenv("SEARCH_TABLE", "project_search")
EMBED_DIMS = int(os.getenv("EMBEDDING_DIMS", "384"))

# ---------- Embeddings (Supabase Edge) ----------
SUPABASE_EMBED_URL = os.getenv("SUPABASE_EMBED_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

def _text_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _concat_text(row: pd.Series) -> str:
    # Ajustá campos según tu DF
    title = str(row.get("title") or "")
    abstract = str(row.get("abstract") or "")
    country = str(row.get("country") or "")
    year = str(row.get("year") or "")
    return " | ".join([title, abstract, country, year]).strip()

def _embed_batch_sync(texts: List[str]) -> List[List[float]]:
    if not SUPABASE_EMBED_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Embeddings no configurados (SUPABASE_EMBED_URL, SUPABASE_SERVICE_ROLE_KEY).")
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            SUPABASE_EMBED_URL,
            headers={"Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}", "Content-Type": "application/json"},
            json={"inputs": texts},
        )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "embeddings" in data:
        return data["embeddings"]
    if isinstance(data, list):
        return data
    raise RuntimeError(f"Formato inesperado del embedder: {data}")

def _ensure_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {SEARCH_TABLE} (
                project_id    BIGINT PRIMARY KEY,
                title         TEXT,
                abstract      TEXT,
                country       TEXT,
                year          INT,
                text_hash     TEXT NOT NULL,
                embedding     VECTOR({EMBED_DIMS})
            )
        """))
        # Índices recomendados (usá uno u otro, o ambos según volumen/latencia)
        conn.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = '{SEARCH_TABLE}_ivf_idx') THEN "
                          f"CREATE INDEX {SEARCH_TABLE}_ivf_idx ON {SEARCH_TABLE} USING ivfflat (embedding vector_l2_ops) WITH (lists = 100); END IF; END $$;"))
        conn.execute(text(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname = '{SEARCH_TABLE}_hnsw_idx') THEN "
                          f"CREATE INDEX {SEARCH_TABLE}_hnsw_idx ON {SEARCH_TABLE} USING hnsw (embedding vector_l2_ops); END IF; END $$;"))

def _fetch_existing_hashes(engine: Engine) -> Dict[int, str]:
    with engine.begin() as conn:
        res = conn.execute(text(f"SELECT project_id, text_hash FROM {SEARCH_TABLE}"))
        return {int(r.project_id): r.text_hash for r in res.fetchall()}

def _upsert_rows(engine: Engine, rows: List[Tuple[int, str, str, str, int, str, List[float]]]) -> int:
    if not rows:
        return 0
    # PG vector requiere casting explícito para arrays → usamos formato '[...]'
    with engine.begin() as conn:
        sql = text(f"""
            INSERT INTO {SEARCH_TABLE} (project_id, title, abstract, country, year, text_hash, embedding)
            VALUES (:project_id, :title, :abstract, :country, :year, :text_hash, :embedding::vector)
            ON CONFLICT (project_id) DO UPDATE
            SET title = EXCLUDED.title,
                abstract = EXCLUDED.abstract,
                country = EXCLUDED.country,
                year = EXCLUDED.year,
                text_hash = EXCLUDED.text_hash,
                embedding = EXCLUDED.embedding
        """)
        payload = []
        for pid, title, abstract, country, year, thash, vec in rows:
            vec_sql = f"[{','.join(map(str, vec))}]"
            payload.append({
                "project_id": pid,
                "title": title,
                "abstract": abstract,
                "country": country,
                "year": year if year is not None else None,
                "text_hash": thash,
                "embedding": vec_sql,
            })
        conn.execute(sql, payload)
    return len(rows)

def main() -> Dict[str, Any]:
    start = time.time()

    # 1) Leer DF desde lake/gold
    df = pd.read_parquet(PROJECTS_PARQUET)
    # normalizar columnas esperadas
    expected = ["projectID", "title", "abstract", "country", "year"]
    for col in expected:
        if col not in df.columns:
            df[col] = None

    df = df.rename(columns={"projectID": "project_id"})
    df["country"] = df.get("country")  # ya existe en tu set
    # 2) Generar texto + hash
    df["__text"] = df.apply(_concat_text, axis=1)
    df["__hash"] = df["__text"].map(_text_hash)

    engine = get_engine()
    _ensure_schema(engine)

    # 3) Buscar existentes para evitar recomputar
    existing = _fetch_existing_hashes(engine)  # project_id -> hash
    to_compute = df[
        (df["project_id"].notna()) &
        (~df["project_id"].astype(int).isin(existing.keys()) |
         (df["project_id"].astype(int).map(existing).fillna("") != df["__hash"]))
    ].copy()

    # 4) Embeddings por lotes
    BATCH = int(os.getenv("EMBED_BATCH", "128"))
    inserts: List[Tuple[int, str, str, str, int, str, List[float]]] = []

    for i in range(0, len(to_compute), BATCH):
        chunk = to_compute.iloc[i:i+BATCH]
        texts = chunk["__text"].tolist()
        vecs = _embed_batch_sync(texts)
        for (idx, row), vec in zip(chunk.iterrows(), vecs):
            inserts.append((
                int(row["project_id"]),
                str(row.get("title") or ""),
                str(row.get("abstract") or ""),
                str(row.get("country") or "") if row.get("country") is not None else None,
                int(row.get("year")) if pd.notna(row.get("year")) else None,
                str(row["__hash"]),
                vec,
            ))

    # 5) Upsert
    n = _upsert_rows(engine, inserts)

    elapsed = time.time() - start
    return {
        "indexed": int(n),
        "seconds": round(elapsed, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    stats = main()
    print(stats)
