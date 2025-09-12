# etl/sync_to_supabase.py
"""
Gold -> Supabase (selectivo)
- run(only=[...]) sincroniza sólo esas tablas.
"""

import os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

DATA_DIR = Path(os.getenv("DATA_DIR", "lake"))
GOLD = DATA_DIR / "gold"

DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    raise RuntimeError("Falta SUPABASE_DB_URL en el entorno.")

TABLES = [
    ("dim_project.parquet",            "dim_project"),
    ("dim_organization.parquet",       "dim_organization"),
    ("fact_funding.parquet",           "fact_funding"),
    ("dim_time.parquet",               "dim_time"),
    ("dim_country.parquet",            "dim_country"),
    ("dim_program.parquet",            "dim_program"),
    ("bridge_project_program.parquet", "bridge_project_program"),
    ("dim_topic.parquet",              "dim_topic"),
    ("bridge_project_topic.parquet",   "bridge_project_topic"),
    ("dim_status.parquet",             "dim_status"),
    ("bridge_project_status.parquet",  "bridge_project_status"),
]

MAX_PARAMS = 60000

def _read_parquet_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"[WARN] No existe {path}; se omite.")
        return pd.DataFrame()
    return pd.read_parquet(path)

def _safe_chunksize(df: pd.DataFrame) -> int:
    cols = max(1, len(df.columns))
    return max(1, MAX_PARAMS // cols)

def _create_indexes(conn):
    stmts = [
        'CREATE INDEX IF NOT EXISTS ix_dim_project_projectid ON dim_project ("projectID");',
        'CREATE INDEX IF NOT EXISTS ix_dim_project_year      ON dim_project (year);',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_organization_org_sk ON dim_organization (org_sk);',
        'CREATE INDEX IF NOT EXISTS ix_dim_organization_organisationid ON dim_organization ("organisationID");',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_time_date_key ON dim_time (date_key);',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_country_country_key ON dim_country (country_key);',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_program_program_id ON dim_program (program_id);',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_topic_topic_id ON dim_topic (topic_id);',
        'CREATE UNIQUE INDEX IF NOT EXISTS ux_dim_status_status_id ON dim_status (status_id);',
        'CREATE INDEX IF NOT EXISTS ix_bpp_project ON bridge_project_program ("projectID");',
        'CREATE INDEX IF NOT EXISTS ix_bpp_prog    ON bridge_project_program (program_id);',
        'CREATE INDEX IF NOT EXISTS ix_bpt_project ON bridge_project_topic ("projectID");',
        'CREATE INDEX IF NOT EXISTS ix_bpt_topic   ON bridge_project_topic (topic_id);',
        'CREATE INDEX IF NOT EXISTS ix_bps_project ON bridge_project_status ("projectID");',
        'CREATE INDEX IF NOT EXISTS ix_bps_status  ON bridge_project_status (status_id);',
        'CREATE INDEX IF NOT EXISTS ix_fact_funding_projectid ON fact_funding ("projectID");',
        'CREATE INDEX IF NOT EXISTS ix_fact_funding_org_sk    ON fact_funding (org_sk);',
        'CREATE INDEX IF NOT EXISTS ix_fact_funding_year      ON fact_funding (year);',
    ]
    for s in stmts:
        try:
            conn.execute(text(s))
        except Exception as e:
            print(f"[INFO] Índice omitido: {e}")

def run(only: list[str] | None = None):
    engine = create_engine(DB_URL, future=True, pool_pre_ping=True, pool_recycle=300)
    selected = [(f,t) for (f,t) in TABLES] if not only else [(f,t) for (f,t) in TABLES if t in set(only)]

    summary = []
    with engine.begin() as conn:
        for filename, table in selected:
            src = GOLD / filename
            df = _read_parquet_safe(src)
            if df.empty:
                summary.append((table, 0, "SKIPPED (no data)"))
                continue
            cs = _safe_chunksize(df)
            df.to_sql(
                table, con=engine, schema="public",
                if_exists="replace", index=False,
                chunksize=cs, method="multi",
            )
            count = conn.execute(text(f'SELECT COUNT(*) FROM "public"."{table}"')).scalar_one()
            summary.append((table, count, f"OK (chunksize={cs})"))

        _create_indexes(conn)

    print("\n[Carga a Supabase] Resumen:")
    for table, count, status in summary:
        print(f" - {table:28s} | rows={count:<8} | {status}")
