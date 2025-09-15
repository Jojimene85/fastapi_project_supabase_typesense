"""
Tests para la conexión con Supabase/Postgres.
Finalidad: Verificar que la función de conexión retorna una sesión válida y que se puede ejecutar una consulta simple.
"""

import pytest
from sqlalchemy import text
from api.services.db import get_engine

def test_db_session():
    """
    Objetivo: Comprobar que get_engine retorna una sesión válida y se puede ejecutar una consulta básica.
    """
    session = get_engine().connect()
    result = session.execute(text("SELECT 1"))
    assert list(result)[0][0] == 1
    session.close()