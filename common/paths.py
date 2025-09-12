# common/paths.py
import os
from pathlib import Path

DATA_DIR   = Path(os.getenv("DATA_DIR", "/lake"))
BRONZE_DIR = Path(os.getenv("BRONZE_DIR", DATA_DIR / "bronze"))
SILVER_DIR = Path(os.getenv("SILVER_DIR", DATA_DIR / "silver"))
GOLD_DIR   = Path(os.getenv("GOLD_DIR",   DATA_DIR / "gold"))

def ensure_dirs() -> None:
    """Crea /bronze /silver /gold si no existen (idempotente)."""
    for d in (BRONZE_DIR, SILVER_DIR, GOLD_DIR):
        d.mkdir(parents=True, exist_ok=True)
