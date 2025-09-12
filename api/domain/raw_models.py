"""
Modelos Pydantic de dominio para CRUD de archivos raw (subir/registrar).
(payloads CRUD raw) - BORRAR
"""

from pydantic import BaseModel, Field

class RawFileIn(BaseModel):
    filename: str = Field(..., description="Nombre del archivo (relativo a lake/bronze)")
    content: str | None = Field(None, description="Contenido en texto plano opcional (para CSV pequeño)")

class RawFileOut(BaseModel):
    ok: bool
    message: str
