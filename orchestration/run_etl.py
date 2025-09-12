import os
from pathlib import Path
from typing import Iterable, Dict, Any, Optional, Set, List
import inspect

# --- Paths y helpers compartidos ---
try:
    from common.paths import BRONZE_DIR, SILVER_DIR, GOLD_DIR, ensure_dirs
except Exception as e:
    # Fallback por si el módulo common no existe, pero NO hacemos full.
    BRONZE_DIR = Path("/lake/bronze")
    SILVER_DIR = Path("/lake/silver")
    GOLD_DIR   = Path("/lake/gold")
    def ensure_dirs():
        for p in (BRONZE_DIR, SILVER_DIR, GOLD_DIR):
            p.mkdir(parents=True, exist_ok=True)

def _log(msg: str) -> None:
    print(msg, flush=True)

# Map de CSV -> fuente silver (ajustá si tus nombres cambian)
FILE2SOURCE = {
    "organization.csv": "organizations",
    "project.csv": "projects",
    "topics.csv": "topics",
    "legalBasis.csv": "legalBasis",
    "policyPriorities.csv": "policyPriorities",
    "euroSciVoc.csv": "euroSciVoc",
    "webItem.csv": "webItem",
    "webLink.csv":  "webLink"
}

# Qué tablas/targets de Gold dependen de cada fuente Silver
# Ajustá según tu pipeline real
GOLD_BY_SOURCE: Dict[str, Set[str]] = {
    "projects": {
        "dim_project", "fact_funding", "dim_status",
        "dim_program", "bridge_project_program",
        "dim_topic", "bridge_project_topic",
        # si tu fact/bridges salen de projects, los agregás aquí
    },
    "organizations": {
        "dim_organization",
        # si tenés puente org-project, etc., agrégalo si se genera en gold
    },
}

def _normalize_changed_files(changed_files: Iterable[str]) -> Set[str]:
    """De una lista de CSV tocados -> set de fuentes silver (organizations, projects, etc.)."""
    sources: Set[str] = set()
    for f in changed_files:
        name = os.path.basename(str(f)).strip()
        src = FILE2SOURCE.get(name)
        if src:
            sources.add(src)
        else:
            _log(f"[runner] WARNING: CSV '{name}' no mapea a ninguna fuente conocida (ignorado).")
    return sources

def _gold_targets_for_sources(sources: Iterable[str]) -> Set[str]:
    """De las fuentes silver afectadas -> targets gold mínimos."""
    targets: Set[str] = set()
    for s in sources:
        targets |= GOLD_BY_SOURCE.get(s, set())
    return targets

def _run_bronze_to_silver(only_sources: Optional[Iterable[str]],
                          bronze_changed_files: Optional[Iterable[str]]) -> None:
    """
    Bronze -> Silver (estrictamente parcial).
    Prioridad:
      1) bronze_to_silver.run_files(changed_files=[...])
      2) bronze_to_silver.run(only=[...])
      3) si ninguna soporta parcial -> ERROR (NO full run)
    """
    from etl import bronze_to_silver as b2s  # import tardío por PYTHONPATH

    files = list(bronze_changed_files or [])
    subset = sorted(set(only_sources or []))

    # 1) Preferimos run_files()
    if hasattr(b2s, "run_files"):
        short = [os.path.basename(p) for p in files]
        _log(f"[b2s] run_files(changed_files={short})")
        return b2s.run_files(changed_files=files)

    # 2) Si no hay run_files, intentamos run(only=...)
    if hasattr(b2s, "run"):
        sig = inspect.signature(b2s.run)
        if "only" in sig.parameters:
            if subset:
                _log(f"[b2s] run(only={subset})")
                return b2s.run(only=subset)
            else:
                _log("[b2s] no hay fuentes para procesar (no-op).")
                return
        else:
            raise RuntimeError(
                "bronze_to_silver.run existe pero no acepta 'only'. "
                "Se requiere ejecución parcial; no se hará run() completo."
            )

    # 3) Nada parcial disponible
    raise RuntimeError(
        "bronze_to_silver no expone ni run_files(changed_files=...) ni run(only=...). "
        "Se requiere implementación parcial."
    )

def _run_silver_to_gold(targets: Optional[Iterable[str]]) -> None:
    """
    Silver -> Gold (estrictamente parcial).
    Prioridad:
      1) silver_to_gold.run_targets(targets=[...])
      2) si no existe -> ERROR (NO full run)
    """
    if not targets:
        _log("[s2g] no hay targets a procesar (no-op).")
        return

    from etl import silver_to_gold as s2g  # import tardío por PYTHONPATH
    tset = sorted(set(targets))

    if hasattr(s2g, "run_targets"):
        _log(f"[s2g] run_targets(targets={tset})")
        return s2g.run_targets(targets=tset)

    # No permitimos full run
    raise RuntimeError(
        "silver_to_gold no expone run_targets(targets=...). "
        "Se requiere ejecución parcial; no se hará run() completo."
    )

def run_subset(changed_files: Iterable[str], **_ignored) -> Dict[str, Any]:
    """
    Ejecuta SOLO lo afectado por los CSV cambiados en Bronze.
    Retorna un dict resumen.
    """
    ensure_dirs()  # crea /lake/* si faltan (idempotente)

    # Sources desde los CSV cambiados
    sources = _normalize_changed_files(changed_files)
    _log(f"[runner] Fuentes silver afectadas: {sorted(sources)}")

    # Paths absolutos a los CSV tocados (para run_files)
    bronze_changed_files = [str(BRONZE_DIR / os.path.basename(p)) for p in changed_files if p]

    # Bronze -> Silver parcial
    if sources:
        _run_bronze_to_silver(only_sources=sources, bronze_changed_files=bronze_changed_files)
    else:
        _log("[runner] No hay fuentes silver para procesar (no-op).")

    # Silver -> Gold parcial
    targets = _gold_targets_for_sources(sources)
    _log(f"[runner] Targets gold a regenerar: {sorted(targets) if targets else []}")
    if targets:
        _run_silver_to_gold(targets)
    else:
        _log("[runner] No hay targets gold a procesar (no-op).")

    return {
        "ok": True,
        "changed": sorted(map(os.path.basename, changed_files)),
        "gold_synced": sorted(targets),
    }

def run_full() -> dict:
    """Ejecuta todo el pipeline: Bronze → Silver → Gold → Supabase."""
    _run_bronze_to_silver(only_sources=None, bronze_changed_files=None)
    _run_silver_to_gold(targets=None)
    # Sincroniza Gold con Supabase
    try:
        from etl.sync_to_supabase import run as sync_supabase_run
        sync_supabase_run()
    except Exception as e:
        return {"ok": False, "error": f"Error en sync_to_supabase: {e}"}
    return {"ok": True, "msg": "Pipeline completo ejecutado"}
