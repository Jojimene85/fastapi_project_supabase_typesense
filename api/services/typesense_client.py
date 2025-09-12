"""
Cliente Typesense con autodetección de host/entorno y soporte para admin/search keys.

Prioridades:
1) Si existe TYPESENSE_HOST en el entorno, se usa (p. ej., "typesense" o "localhost").
2) Si no existe:
   - Si estamos dentro de Docker (/.dockerenv), se usa "typesense".
   - Si no, se usa "localhost".

Además:
- TYPESENSE_PORT (default 8108)
- TYPESENSE_PROTOCOL (default "http")
- TYPESENSE_API_KEY  (admin)   -> para init/index
- TYPESENSE_SEARCH_KEY (read)  -> para solo consultas
"""

import os
from pathlib import Path
import typesense


def _running_in_docker() -> bool:
    """Heurística: presencia de /.dockerenv -> contenedor Docker."""
    return Path("/.dockerenv").exists()


def _resolve_host() -> str:
    """Determina el host de Typesense según entorno y variables."""
    env_host = os.getenv("TYPESENSE_HOST")
    if env_host:
        return env_host  # prioridad absoluta

    # Autodetección
    if _running_in_docker():
        return "typesense"  # nombre del servicio en docker-compose
    return "localhost"      # ejecución local fuera de docker


def _resolve_port() -> str:
    return os.getenv("TYPESENSE_PORT", "8108")


def _resolve_protocol() -> str:
    # Cambiá a "https" si configurás TLS o usás Typesense Cloud
    return os.getenv("TYPESENSE_PROTOCOL", "http")


def _build_client(api_key: str) -> typesense.Client:
    """Crea un cliente Typesense con la api_key indicada."""
    host = _resolve_host()
    port = _resolve_port()
    protocol = _resolve_protocol()

    return typesense.Client({
        "nodes": [{"host": host, "port": port, "protocol": protocol}],
        "api_key": api_key,
        "connection_timeout_seconds": 5,
    })


def get_admin_client() -> typesense.Client:
    """
    Cliente con permisos de administración (crear colecciones, indexar, borrar).
    Usa TYPESENSE_API_KEY.
    """
    key = os.getenv("TYPESENSE_API_KEY")
    if not key:
        raise RuntimeError("Falta TYPESENSE_API_KEY en el entorno (admin key).")
    return _build_client(key)


def get_search_client() -> typesense.Client:
    """
    Cliente solo-lectura para búsquedas.
    Usa TYPESENSE_SEARCH_KEY si está seteada; si no, cae en TYPESENSE_API_KEY.
    """
    key = os.getenv("TYPESENSE_SEARCH_KEY") or os.getenv("TYPESENSE_API_KEY")
    if not key:
        raise RuntimeError("Falta TYPESENSE_SEARCH_KEY o TYPESENSE_API_KEY en el entorno.")
    return _build_client(key)


# Para compatibilidad con el resto del código:
# - Usamos admin por defecto (init/index necesitan permisos).
client = get_admin_client()

