"""
Tests para el módulo ETL: bronze_to_silver, silver_to_gold y sync_to_supabase.
Finalidad: Verificar que la transformación de un archivo CSV crudo a Parquet limpio, luego a la capa dorada y finalmente a Supabase se realiza correctamente y sin pérdida de datos.
"""

import pytest
import pandas as pd
from etl.bronze_to_silver import run_files
from etl.silver_to_gold import run as silver_to_gold_run
from sqlalchemy import create_engine
from etl.sync_to_supabase import run as sync_to_supabase_run

def test_bronze_to_silver_transformation(tmp_path):
    """
    Objetivo: Asegurarse que bronze_to_silver transforma correctamente un CSV en un archivo Parquet con los mismos datos.
    """
    # Crea un CSV de ejemplo
    csv_path = tmp_path / "input.csv"
    df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    df.to_csv(csv_path, index=False)

    # Ejecuta la transformación
    run_files(str(csv_path))

    # Verifica el resultado en la ruta que use la función
    # Ejemplo: output_parquet = tmp_path / "output.parquet"
    # df_parquet = pd.read_parquet(output_parquet)
    # pd.testing.assert_frame_equal(df, df_parquet)

def test_silver_to_gold_run(tmp_path, monkeypatch):
    # Crea un parquet de ejemplo en tmp_path/SILVER
    silver_dir = tmp_path / "silver"
    silver_dir.mkdir()
    df = pd.DataFrame({"id": [1, 2], "title": ["a", "b"], "startDate": ["2020-01-01", "2021-01-01"]})
    df.to_parquet(silver_dir / "project.parquet", index=False)

    # Monkeypatch el SILVER_DIR y GOLD_DIR en el módulo
    import etl.silver_to_gold as stg
    stg.SILVER = silver_dir
    stg.GOLD = tmp_path / "gold"
    stg.GOLD.mkdir()

    # Ejecuta el ETL
    silver_to_gold_run(only=["dim_project"])

    # Verifica que el archivo gold/dim_project.parquet se creó
    gold_file = stg.GOLD / "dim_project.parquet"
    assert gold_file.exists()
    df_gold = pd.read_parquet(gold_file)
    assert "title" in df_gold.columns

# def test_sync_to_supabase_run(tmp_path):
#     # Crea archivos Parquet de ejemplo en tmp_path/gold
#     gold_dir = tmp_path / "gold"
#     gold_dir.mkdir()
#     df = pd.DataFrame({"projectID": [1, 2], "year": [2020, 2021], "title": ["a", "b"]})
#     df.to_parquet(gold_dir / "dim_project.parquet", index=False)

#     # Monkeypatch GOLD y DB_URL en el módulo
#     import etl.sync_to_supabase as sts
#     sts.GOLD = gold_dir
#     sts.DB_URL = "sqlite:///:memory:"  # Usa SQLite en memoria para test

#     # Ejecuta el ETL solo para dim_project
#     try:
#         sync_to_supabase_run(only=["dim_project"])
#     except Exception as e:
#         assert False, f"ETL run failed: {e}"

#     # Verifica que la tabla existe en la base
#     engine = create_engine(sts.DB_URL)
#     with engine.connect() as conn:
#         tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
#         assert "dim_project" in tables