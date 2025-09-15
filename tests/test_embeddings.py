"""
Tests para la lógica de embeddings y vectorización.
Finalidad: Verificar que el proceso de generación de embeddings y su indexación en Typesense funciona correctamente.
"""

import pytest
from etl.index_projects_typesense import main

def test_etl_main_runs():
    """
    Testea que el ETL principal corre sin errores y retorna un dict con 'indexed'.
    """
    result = main()
    assert isinstance(result, dict)
    assert "indexed" in result
    assert isinstance(result["indexed"], int)