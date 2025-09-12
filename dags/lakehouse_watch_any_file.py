from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

import pendulum
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor
from datetime import timedelta

# -----------------------------
# Config de paths por entorno
# -----------------------------
def get_dirs() -> Dict[str, Path]:
    data_dir = Path(os.getenv("DATA_DIR", "/lake"))
    bronze   = Path(os.getenv("BRONZE_DIR", str(data_dir / "bronze")))
    silver   = Path(os.getenv("SILVER_DIR", str(data_dir / "silver")))
    gold     = Path(os.getenv("GOLD_DIR",   str(data_dir / "gold")))
    for d in (bronze, silver, gold):
        d.mkdir(parents=True, exist_ok=True)
    return {"DATA_DIR": data_dir, "BRONZE_DIR": bronze, "SILVER_DIR": silver, "GOLD_DIR": gold}

def list_bronze_csvs(bronze_dir: Path) -> List[Path]:
    return sorted(bronze_dir.glob("*.csv"))

# -----------------------------
# Sensor: detecta cambios por mtime
# -----------------------------
VAR_MTIMES_KEY = "lake_bronze_mtimes"

def _load_prev_mtimes() -> Dict[str, float]:
    raw = Variable.get(VAR_MTIMES_KEY, default_var="{}")
    try:
        return json.loads(raw)
    except Exception:
        return {}

def _current_mtimes(files: List[Path]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for f in files:
        try:
            out[f.name] = f.stat().st_mtime
        except FileNotFoundError:
            pass
    return out

def wait_for_bronze_updates(**context) -> bool:
    dirs = get_dirs()
    bronze_dir: Path = dirs["BRONZE_DIR"]
    files = list_bronze_csvs(bronze_dir)

    ti = context["ti"]
    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}
    force = bool(conf.get("force"))

    curr = _current_mtimes(files)
    prev = _load_prev_mtimes()

    if force:
        changed = sorted(curr.keys())
    else:
        changed = sorted([name for name, m in curr.items() if m > float(prev.get(name, 0.0))])

    ti.xcom_push(key="changed", value=changed)
    ti.xcom_push(key="mtimes", value=curr)

    if force:
        print("[sensor] Forzado por conf.force = true; se continuará aunque no haya cambios.")
        return True

    if changed:
        print(f"[sensor] Cambios detectados en bronze: {changed}")
        return True

    print("[sensor] Sin cambios; reintenta en el próximo poke.")
    return False

# -----------------------------
# Tarea ETL parcial (subset)
# -----------------------------
def run_etl_subset(**context):
    dirs = get_dirs()
    bronze_dir: Path = dirs["BRONZE_DIR"]
    silver_dir: Path = dirs["SILVER_DIR"]
    gold_dir: Path   = dirs["GOLD_DIR"]

    ti = context["ti"]
    dag_run = context.get("dag_run")
    conf = (dag_run.conf or {}) if dag_run else {}

    changed = ti.xcom_pull(task_ids="wait_for_bronze_updates", key="changed") or []
    mtimes  = ti.xcom_pull(task_ids="wait_for_bronze_updates", key="mtimes") or {}

    if conf.get("force") and not changed:
        changed = sorted([p.name for p in list_bronze_csvs(bronze_dir)])

    print(f"[runner] Ejecutando run_subset para: {changed}")

    try:
        from orchestration.run_etl import run_subset
    except Exception as e:
        print("[runner] ERROR importando orchestration.run_etl.run_subset:", e)
        raise

    # run_subset SOLO acepta changed_files
    result = run_subset(changed_files=changed)

    if isinstance(result, dict):
        print(f"[runner] OK. Gold sincronizado: {result.get('gold_synced', [])}")
    else:
        print("[runner] ETL subset finalizado.")

    if mtimes:
        try:
            Variable.set(VAR_MTIMES_KEY, json.dumps(mtimes))
            print(f"[mtimes] Variable '{VAR_MTIMES_KEY}' actualizada con {len(mtimes)} entradas.")
        except Exception as e:
            print("[mtimes] Advertencia: no se pudo persistir Variable:", e)

    return {"ok": True, "changed": changed, "gold_dir": str(gold_dir)}

def index_to_typesense():
    # Llama al script ETL que indexa proyectos y genera embeddings
    from etl.index_projects_typesense import main
    main()

# -----------------------------
# Definición del DAG
# -----------------------------
default_args = {"owner": "airflow", "depends_on_past": False, "retries": 0, "retry_delay": timedelta(minutes=1)}

with DAG(
    dag_id="lakehouse_watch_any_file",
    description="Sensor de cambios en bronze + ETL subset + vectorización Typesense",
    default_args=default_args,
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule="@continuous",
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "bronze", "etl", "typesense"],
) as dag:

    wait_for_bronze = PythonSensor(
        task_id="wait_for_bronze_updates",
        python_callable=wait_for_bronze_updates,
        poke_interval=15,
        timeout=60 * 60 * 24,
        mode="reschedule",
        doc="Espera cambios en archivos CSV del layer Bronze.",
    )

    etl_subset = PythonOperator(
        task_id="run_etl_subset",
        python_callable=run_etl_subset,
        doc="Ejecuta sólo las transformaciones necesarias para los archivos modificados.",
    )

    ts_index = PythonOperator(
        task_id="index_to_typesense",
        python_callable=index_to_typesense,
        doc="Indexa proyectos en Typesense con embeddings.",
    )

    wait_for_bronze >> etl_subset >> ts_index

