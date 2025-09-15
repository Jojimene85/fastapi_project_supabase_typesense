"""
Tests para la API REST (FastAPI).
Finalidad: Verificar que los endpoints principales están accesibles y responden correctamente, incluyendo autenticación básica.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_read_main():
    """
    Objetivo: Comprobar que el endpoint raíz ("/") responde con status 200.
    """
    response = client.get("/")
    assert response.status_code == 200

def test_auth_required():
    """
    Objetivo: Verificar que el endpoint /seed exige autenticación (debe devolver 401 si no se provee usuario/contraseña).
    """
    response = client.post("/seed")
    assert response.status_code == 401  # O el código esperado para auth