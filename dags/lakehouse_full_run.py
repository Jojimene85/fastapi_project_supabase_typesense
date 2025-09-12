from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import timedelta
import pendulum
# --- force PYTHONPATH for tasks ---
import os, sys
paths = ["/opt/airflow", "/opt/airflow/ext", "/opt/airflow/api"]
for p in paths:
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["PYTHONPATH"] = ":".join(paths + [os.environ.get("PYTHONPATH", "")])
# ----------------------------------

def run_full_etl():
    from orchestration.run_etl import run_full
    run_full()

def index_projects_typesense():
    from etl.index_projects_typesense import main
    main()

default_args = {"owner": "airflow", "retries": 0, "retry_delay": timedelta(minutes=1)}

with DAG(
    dag_id="lakehouse_full_run",
    description="Ejecuta todo el pipeline + vectorización Typesense",
    default_args=default_args,
    start_date=pendulum.datetime(2024, 1, 1, tz="UTC"),
    schedule=None,  # Solo manual
    catchup=False,
    tags=["lakehouse", "full", "typesense"],
) as dag:
    etl_task = PythonOperator(task_id="run_full_etl", python_callable=run_full_etl)
    index_task = PythonOperator(task_id="index_projects_typesense", python_callable=index_projects_typesense)
    etl_task >> index_task