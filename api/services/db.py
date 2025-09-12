"""
Conexión a Supabase/Postgres mediante SQLAlchemy Engine sincrónico y asíncrono.
y asincrónico.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

DB_URL = os.getenv("SUPABASE_DB_URL")

def get_engine():
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL no configurado")
    # pool_pre_ping evita conexiones muertas
    return create_engine(db_url, pool_pre_ping=True, echo=False)

def get_async_engine() -> AsyncEngine:
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("Falta SUPABASE_DB_URL")
    sync_url = make_url(db_url)  # parsea seguro (respeta % y caracteres especiales)
    async_url = sync_url.set(drivername="postgresql+asyncpg")
    return create_async_engine(str(async_url), future=True, pool_pre_ping=True)

