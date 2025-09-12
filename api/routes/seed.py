from fastapi import APIRouter
import requests
import os
from requests.auth import HTTPBasicAuth

router = APIRouter(prefix="/seed", tags=["seed"])

AIRFLOW_URL = os.getenv("AIRFLOW_API_URL", "http://airflow-webserver:8080/api/v1")
DAG_ID = "lakehouse_full_run"
AIRFLOW_USER = os.getenv("AIRFLOW_ADMIN_USER", "airflow")
AIRFLOW_PASS = os.getenv("AIRFLOW_ADMIN_PASSWORD", "admin")

@router.post("/")
def seed_everything():
    """Trigger Airflow DAG for full load + vectorization."""
    url = f"{AIRFLOW_URL}/dags/{DAG_ID}/dagRuns"
    headers = {"Content-Type": "application/json"}
    payload = {"conf": {"trigger": "full"}}
    print("Triggering Airflow DAG:", url, payload, headers)  # <-- print antes del request
    try:
        resp = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASS)
        )
        print("Airflow response:", resp.status_code, resp.text)  # <-- print después del request
        resp.raise_for_status()
        return {
            "status": "ok",
            "msg": "DAG lakehouse_full_run triggered",
            "airflow_response": resp.json()
        }
    except Exception as e:
        print("Error details:", str(e))
        print("Airflow response:", getattr(resp, "text", None))
        return {
            "status": "error",
            "details": str(e),
            "airflow_response": getattr(resp, "text", None)
        }


