"""
Modelos Pydantic para respuestas de la capa Gold.
"""

from pydantic import BaseModel
from typing import Any

class ProjectOut(BaseModel):
    project_id: str | None
    title: str | None
    abstract: str | None
    program: str | None
    country: str | None
    year: int | None

class SearchResult(BaseModel):
    hits: Any  # Estructura propia de Typesense
