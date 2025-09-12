"""
Basic Auth simple para proteger la API (cumple requisito obligatorio).
"""
# api/auth.py
import os, secrets
from fastapi import HTTPException, status, Security
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_security = HTTPBasic()  # Swagger agrega el esquema Basic

def basic_auth(credentials: HTTPBasicCredentials = Security(_security)):
    user = os.getenv("BASIC_AUTH_USER")
    pwd  = os.getenv("BASIC_AUTH_PASS")

    if not user or not pwd:
        raise HTTPException(
            status_code=500,
            detail="Credenciales BASIC_AUTH_USER/BASIC_AUTH_PASS no configuradas en el entorno",
        )

    if not (
        secrets.compare_digest(credentials.username, user)
        and secrets.compare_digest(credentials.password, pwd)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

