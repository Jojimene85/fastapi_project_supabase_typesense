# Lakehouse (pandas) – EU Research Projects

> Proyecto de prueba técnica que implementa una arquitectura tipo **Lakehouse** con **pandas + Parquet**, **Supabase (Postgres)** como DWH, **Typesense** para búsqueda y **FastAPI** como API.  
> Incluye **Airflow standalone** (webserver + scheduler + sqlite en 1 contenedor) con **sensor** que dispara el pipeline al actualizarse un archivo en Bronze.

---

## 🌍 Contexto de los datos

Los datasets provienen de **proyectos de investigación científica en Europa** (ej. programas Horizon 2020, FP7).  
Incluyen información de:

- **Proyectos**: título, abstract, país, programa, fechas, financiación.
- **Organizaciones**: entidades participantes, sector, país.
- **Temas (topics)**: taxonomía científica asignada.
- **Prioridades de política**: alineación con ejes de la UE.
- **Base legal**: marco jurídico que sustenta el proyecto.
- **Vocabularios científicos (euroSciVoc)**: clasificaciones temáticas.
- **Web items y links**: recursos digitales asociados.

Estos archivos alimentan la **capa Bronze**, y el pipeline construye una vista **star schema** en Gold con dimensiones y un hecho de financiación.

---

## 🧭 Arquitectura

- **Data Lake local (filesystem)**  
  - `data/bronze/` → archivos crudos (CSV)  
  - `data/silver/` → datos limpios/normalizados en **Parquet**  
  - `data/gold/` → **esquema estrella** en **Parquet**

- **ETL**: Python + pandas  
  - `bronze_to_silver.py` → limpieza/normalización  
  - `silver_to_gold.py` → modelado en esquema estrella  
  - `sync_to_supabase.py` → carga en Postgres (Supabase)

- **Orquestación**:  
  - `orchestration/run_etl.py` → **SSOT** con `run_all()`  
  - Airflow (`lakehouse_watch_fixed_file.py`) → sensor que vigila cambios en Bronze

- **API (FastAPI)**  
  - `/seed` → dispara el pipeline completo  
  - `/raw` → CRUD de archivos en Bronze  
  - `/gold` → queries sobre tablas en Supabase  
  - `/search` → búsqueda en Typesense

- **Search**: Typesense  
  - Indexa proyectos (dim_project) para búsqueda de texto y facetas por país/año.

---

## 📂 Archivos y Carpetas

```
.
├─ api/                        # API FastAPI
│  ├─ main.py                  # Arranca la API y registra routers
│  ├─ auth.py                  # Basic Auth (usuario/contraseña)
│  ├─ routes/                  # Endpoints
│  │  ├─ seed.py               # /seed → corre run_all()
│  │  ├─ raw.py                # /raw → CRUD en Bronze
│  │  ├─ gold.py               # /gold → queries a Supabase
│  │  └─ search.py             # /search → init, index, query en Typesense
│  ├─ services/                # Conexiones externas
│  │  ├─ db.py                 # Conexión SQLAlchemy a Supabase/Postgres
│  │  └─ typesense_client.py   # Cliente Typesense
│  └─ domain/                  # Modelos Pydantic
│     ├─ raw_models.py
│     └─ gold_models.py
│
├─ etl/                        # ETLs en pandas
│  ├─ bronze_to_silver.py      # CSV → Parquet (Silver)
│  ├─ silver_to_gold.py        # Silver → esquema estrella (Gold)
│  └─ sync_to_supabase.py      # Gold → Supabase (truncate & load)
│
├─ orchestration/
│  └─ run_etl.py               # Función run_all(), usada por /seed y DAG
│
├─ dags/
│  └─ lakehouse_watch_fixed_file.py # DAG con sensor por archivo fijo
│
├─ data/
│  ├─ bronze/                  # Archivos crudos
│  ├─ silver/                  # Parquet normalizados
│  └─ gold/                    # Parquet star schema
│
├─ logs/, plugins/             # Carpetas usadas por Airflow
├─ .vol/                       # Persistencia (Typesense, etc.)
│
├─ docker-compose.yml          # Orquesta API, Typesense y Airflow
├─ Dockerfile                  # Imagen de la API
├─ requirements.txt            # Dependencias Python
├─ .dockerignore               # Exclusiones para Docker build
├─ Makefile                    # Atajos de comandos (make up, make seed, etc.)
└─ README.md                   # Este archivo
```

---

## 🚀 Puesta en marcha (simple)

1. Crear carpetas necesarias:
   ```bash
   mkdir -p dags orchestration etl data/bronze data/silver data/gold logs plugins .vol/typesense
   ```

2. Colocar CSVs en `data/bronze/` (ej. `project.csv` con nombre fijo).

3. Levantar servicios:
   ```bash
   docker compose up -d --build
   ```

4. API:
   ```bash
   curl -u admin:supersecret -X POST http://localhost:8000/seed
   ```

5. Airflow UI: [http://localhost:8080](http://localhost:8080)  
   - Activar DAG `lakehouse_watch_fixed_file`.  
   - El DAG detecta cambios en `project.csv` y dispara full reload.

---

## ✅ Checklist

- [x] Bronze/Silver/Gold con pandas  
- [x] Supabase/Postgres como DWH  
- [x] Esquema estrella (dims + fact)  
- [x] API FastAPI con Basic Auth  
- [x] Typesense para búsqueda facetada  
- [x] Airflow (standalone) con sensor de archivo fijo  

---

## 💬 Nota final

Este proyecto simplifica la arquitectura para fines de demo, pero los patrones son **directamente migrables a Databricks**:  
- Parquet → Delta Lake  
- pandas → PySpark  
- Airflow → Jobs/Workflows/DLT  
- Supabase → SQL Warehouse  
