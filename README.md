# Lakehouse (pandas) – EU Research Projects

> Arquitectura Lakehouse con **pandas + Parquet**, **Supabase (Postgres)** como DWH, **Typesense** para búsqueda vectorial y **FastAPI** como API.
> Orquestación con **Airflow** (sensor de archivos y full pipeline).
> Incluye indexación de proyectos con embeddings (vectorización) para búsqueda semántica.

---

## 🧭 Arquitectura General

- **Data Lake local (filesystem)**
  - `lake/bronze/` → archivos crudos (CSV)
  - `lake/silver/` → datos limpios/normalizados (Parquet)
  - `lake/gold/` → modelo estrella (Parquet)
- **ETL modular (Python + pandas)**
  - Limpieza, normalización, modelado y carga a Supabase/Postgres
  - Indexación en Typesense con embeddings (vectorización)
- **Orquestación**
  - Airflow con dos DAGs:
    - `lakehouse_watch_any_file.py`: ejecuta ETL selectivo al detectar cambios en Bronze
    - `lakehouse_full_run.py`: ejecuta pipeline completo + vectorización
- **API REST (FastAPI)**
  - Endpoints para consulta, búsqueda, seed (disparar pipeline), CRUD de archivos
  - Búsqueda avanzada por texto y facetas usando Typesense

---

## 📂 Estructura del Proyecto

```
.
├─ api/                        # FastAPI: endpoints REST, autenticación, servicios
│  ├─ main.py
│  ├─ auth.py
│  ├─ routes/
│  │  ├─ seed.py               # /seed → dispara pipeline completo vía Airflow
│  │  ├─ raw.py                # /raw → CRUD en Bronze
│  │  ├─ gold.py               # /gold → queries sobre Gold/Supabase
│  │  └─ search.py             # /search → init, index, query en Typesense
│  ├─ services/
│  │  ├─ db.py                 # Conexión SQLAlchemy a Supabase/Postgres
│  │  └─ typesense_client.py   # Cliente Typesense
│  └─ domain/                  # Modelos Pydantic
│     ├─ raw_models.py
│     └─ gold_models.py
│
├─ etl/                        # Scripts ETL
│  ├─ bronze_to_silver.py      # CSV → Parquet (Silver)
│  ├─ silver_to_gold.py        # Silver → Gold (star schema)
│  ├─ sync_to_supabase.py      # Gold → Supabase (truncate & load)
│  └─ index_projects_typesense.py # Gold → Typesense (vectorización)
│
├─ orchestration/
│  └─ run_etl.py               # Funciones para ejecutar pipeline completo o selectivo
│
├─ dags/
│  ├─ lakehouse_watch_any_file.py # DAG: sensor de cambios en Bronze + ETL selectivo + vectorización
│  └─ lakehouse_full_run.py       # DAG: pipeline completo + vectorización
│
├─ lake/
│  ├─ bronze/                  # Archivos crudos
│  ├─ silver/                  # Parquet normalizados
│  └─ gold/                    # Parquet star schema
│
├─ typesense-data/             # Persistencia de Typesense (volumen Docker)
├─ airflow-logs/               # Logs de Airflow
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ .env
└─ README.md
```

---

## 🚀 Puesta en marcha

1. **Prepara carpetas persistentes:**

   ```bash
   mkdir -p lake/bronze lake/silver lake/gold typesense-data dags airflow-logs
   ```
2. **Coloca los archivos CSV en `lake/bronze/`**Ejemplo: `project.csv`, `organization.csv`, `topics.csv`, etc.
3. **Configura variables en `.env`**Incluye credenciales de Supabase/Postgres y Typesense.

   Ejemplo de `.env`:

   ```
   SUPABASE_DB_URL=postgresql://user:password@host:5432/dbname
   TYPESENSE_API_KEY=your_typesense_api_key
   AIRFLOW_API_URL=http://localhost:8080/api/v1
   AIRFLOW_API_TOKEN=your_airflow_token
   ```
4. **Levanta los servicios:**

   ```bash
   docker compose up --build
   ```
5. **Accede a los servicios:**

   - **API:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Airflow:** [http://localhost:8080](http://localhost:8080)
   - **Typesense:** [http://localhost:8108](http://localhost:8108)

---

## 🛠️ ETL y Vectorización

- **bronze_to_silver.py:**Limpia y normaliza los datos crudos de Bronze a Silver (Parquet).
- **silver_to_gold.py:**Modela los datos Silver en un esquema estrella Gold (Parquet).
- **sync_to_supabase.py:**Carga las tablas Gold en Supabase/Postgres para consultas SQL y API.
- **index_projects_typesense.py:**
  Lee proyectos Gold, genera embeddings con un modelo transformer y los indexa en Typesense para búsqueda semántica y facetada.

---

## ⚡ Orquestación (Airflow)

- **lakehouse_watch_any_file.py:**

  - Sensor detecta cambios en archivos Bronze.
  - Ejecuta ETL solo para los archivos modificados.
  - Vectoriza e indexa proyectos nuevos en Typesense.
- **lakehouse_full_run.py:**

  - Ejecuta el pipeline completo (Bronze → Silver → Gold → Supabase).
  - Vectoriza e indexa todos los proyectos en Typesense.

---

## 🌐 API REST (FastAPI)

### Endpoints principales

- **`/seed`**`POST /seed`Dispara el DAG `lakehouse_full_run` vía Airflow para ejecutar el pipeline completo y vectorización.
- **`/raw`**CRUD de archivos en Bronze (subida, listado, borrado).
- **`/gold/projects`**Consulta proyectos en Gold/Supabase, filtrando por país y año.
- **`/search`**

  - `POST /search/init` : Inicializa la colección en Typesense.
  - `POST /search/index`: Indexa proyectos Gold en Typesense (incluye embeddings).
  - `GET /search`       : Búsqueda por texto y filtros (país, año, facetas).

### Ejemplo de uso

```bash
# Disparar pipeline completo
curl -u admin:supersecret -X POST http://localhost:8000/seed

# Inicializar colección de búsqueda
curl -u admin:supersecret -X POST http://localhost:8000/search/init

# Indexar proyectos en Typesense
curl -u admin:supersecret -X POST http://localhost:8000/search/index

# Buscar proyectos
curl -u admin:supersecret "http://localhost:8000/search?q=ai&country=DE&year=2023"
```

---

## 🧩 Configuración avanzada

- **Persistencia de Typesense:**Usa solo la carpeta `typesense-data` como volumen Docker.Si necesitas limpiar el índice, puedes borrar la carpeta y reiniciar el servicio.
- **Variables de entorno:**Ajusta `.env` para tus credenciales y rutas.Puedes cambiar el puerto de la API, la URL de Airflow, etc.
- **Embeddings:**El script `index_projects_typesense.py` usa un modelo transformer (ej. `sentence-transformers`) para generar vectores.Puedes cambiar el modelo en el script según tus necesidades.
- **Airflow:**
  La API `/seed` dispara el DAG `lakehouse_full_run` usando la API REST de Airflow.
  Asegúrate de que Airflow tenga la API habilitada y el DAG esté en la carpeta `dags/`.

---

## ✅ Checklist de la Solución

- [X] Arquitectura Medallion (Bronze/Silver/Gold)
- [X] ETL modular y reproducible
- [X] Data warehouse relacional (Supabase/Postgres)
- [X] Modelo estrella en Gold
- [X] API REST con autenticación básica
- [X] Búsqueda vectorial y facetada en Typesense
- [X] Orquestación con Airflow (sensor + full pipeline)
- [X] Indexación con embeddings (transformer)
- [X] Docker Compose para levantar todo el stack

---

## 💬 Notas finales

- El pipeline y la arquitectura son fácilmente migrables a entornos cloud (Databricks, Delta Lake, etc.).
- Puedes ampliar la búsqueda vectorial, agregar facetas o sumar endpoints según tus necesidades.
- La persistencia de Typesense debe estar en la carpeta `typesense-data` (ver `docker-compose.yml`).

---


## 🧭 Diagramas (Mermaid)

### 1) Lakehouse Global

```mermaid
flowchart LR
  subgraph Source["Source (CSV/JSON/PDF)"]
    A[project.csv]
    B[organization.csv]
    C[topics.csv]
    D[policyPriorities.csv]
    E[legalBasis.csv]
    F[euroSciVoc.csv]
    G[webItem.csv]
    H[webLink.csv]
  end

  A & B & C & D & E & F & G & H --> BR[Bronze (Filesystem)]
  BR -->|pandas ETL| SI[Silver (Parquet)]
  SI -->|modelado estrella| GO[Gold (Parquet)]

  GO -->|sync to_sql| DB[(Supabase / Postgres)]
  GO -->|index docs| VS[(Typesense)]

  subgraph API["FastAPI (Basic Auth)"]
    R1[/seed/]
    R2[/raw/]
    R3[/gold/.../]
    R4[/search/]
  end

  R1 --> BR
  R3 --> DB
  R4 --> VS
```

### 2) Bronze (Landing)

```mermaid
flowchart TB
  subgraph Bronze["Bronze (raw)"]
    P1[project.csv]
    P2[organization.csv]
    P3[topics.csv]
    P4[policyPriorities.csv]
    P5[legalBasis.csv]
    P6[euroSciVoc.csv]
    P7[webItem.csv]
    P8[webLink.csv]
  end
```

### 3) Silver (Conformed)

```mermaid
flowchart TB
  subgraph Silver["Silver (cleaned Parquet)"]
    S1[project.parquet\n- tipos normalizados\n- fechas tipadas\n- duration_days]
    S2[organization.parquet]
    S3[topics.parquet]
    S4[policyPriorities.parquet]
    S5[legalBasis.parquet]
    S6[euroSciVoc.parquet]
    S7[webItem.parquet]
    S8[webLink.parquet]
  end
```

### 4) Gold (Star Schema)

```mermaid
erDiagram
  DIM_PROJECT {
    bigint project_sk PK
    string project_id
    string title
    string abstract
    string program
    string country
    date   start_date
    date   end_date
    int    duration_days
    int    year
  }

  DIM_ORGANIZATION {
    bigint org_sk PK
    string org_id
    string org_name
    string org_type
    string org_country
  }

  DIM_TOPIC {
    bigint topic_sk PK
    string topic_code
    string topic_label
  }

  DIM_POLICY_PRIORITY {
    bigint priority_sk PK
    string code
    string label
  }

  DIM_LEGAL_BASIS {
    bigint legal_sk PK
    string code
    string label
  }

  FACT_PROJECT_FUNDING {
    bigint fact_id PK
    bigint project_sk FK
    bigint org_sk FK
    bigint topic_sk FK
    bigint priority_sk FK
    bigint legal_sk FK
    double funding_amount
    int    duration_days
    int    num_web_items
    int    num_links
  }

  DIM_PROJECT ||--o{ FACT_PROJECT_FUNDING : has
  DIM_ORGANIZATION ||--o{ FACT_PROJECT_FUNDING : has
  DIM_TOPIC ||--o{ FACT_PROJECT_FUNDING : has
  DIM_POLICY_PRIORITY ||--o{ FACT_PROJECT_FUNDING : has
  DIM_LEGAL_BASIS ||--o{ FACT_PROJECT_FUNDING : has
```

---

## 📜 Licencia

MIT (o la que prefieras).
