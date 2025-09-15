"""
Conexión a Supabase/Postgres mediante SQLAlchemy Engine sincrónico y asíncrono.
"""

import os
from sqlalchemy import create_engine

def get_engine():
    """
    Retorna un SQLAlchemy Engine usando la URL de la base de datos configurada en .env.
    """
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        raise RuntimeError("SUPABASE_DB_URL no configurada en el entorno")
    return create_engine(db_url, pool_pre_ping=True, echo=False)

