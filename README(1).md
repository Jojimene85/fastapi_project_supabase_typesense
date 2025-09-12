# Lakehouse (pandas) – EU Research Projects

> Lakehouse architecture with **pandas + Parquet**, **Supabase (Postgres)** as DWH, **Typesense** for vector search, and **FastAPI** as API.
> Orchestration with **Airflow** (file sensor and full pipeline).
> Includes project indexing with embeddings (vectorization) for semantic search.

---

## 🧭 General Architecture

- **Local Data Lake (filesystem)**
  - `lake/bronze/` → raw files (CSV)
  - `lake/silver/` → cleaned/normalized data (Parquet)
  - `lake/gold/` → star schema (Parquet)
- **Modular ETL (Python + pandas)**
  - Cleaning, normalization, modeling, and loading to Supabase/Postgres
  - Indexing in Typesense with embeddings (vectorization)
- **Orchestration**
  - Airflow with two DAGs:
    - `lakehouse_watch_any_file.py`: runs selective ETL when changes are detected in Bronze
    - `lakehouse_full_run.py`: runs the full pipeline + vectorization
- **REST API (FastAPI)**
  - Endpoints for querying, searching, seeding (trigger pipeline), and CRUD for files
  - Advanced text and facet search using Typesense

---

## 📂 Project Structure

```
.
├─ api/                        # FastAPI: REST endpoints, authentication, services
│  ├─ main.py
│  ├─ auth.py
│  ├─ routes/
│  │  ├─ seed.py               # /seed → triggers full pipeline via Airflow
│  │  ├─ raw.py                # /raw → CRUD in Bronze
│  │  ├─ gold.py               # /gold → queries on Gold/Supabase
│  │  └─ search.py             # /search → init, index, query in Typesense
│  ├─ services/
│  │  ├─ db.py                 # SQLAlchemy connection to Supabase/Postgres
│  │  └─ typesense_client.py   # Typesense client
│  └─ domain/                  # Pydantic models
│     ├─ raw_models.py
│     └─ gold_models.py
│
├─ etl/                        # ETL scripts
│  ├─ bronze_to_silver.py      # CSV → Parquet (Silver)
│  ├─ silver_to_gold.py        # Silver → Gold (star schema)
│  ├─ sync_to_supabase.py      # Gold → Supabase (truncate & load)
│  └─ index_projects_typesense.py # Gold → Typesense (vectorization)
│
├─ orchestration/
│  └─ run_etl.py               # Functions to run full or selective pipeline
│
├─ dags/
│  ├─ lakehouse_watch_any_file.py # DAG: file sensor in Bronze + selective ETL + vectorization
│  └─ lakehouse_full_run.py       # DAG: full pipeline + vectorization
│
├─ lake/
│  ├─ bronze/                  # Raw files
│  ├─ silver/                  # Normalized Parquet
│  └─ gold/                    # Star schema Parquet
│
├─ typesense-data/             # Typesense persistence (Docker volume)
├─ airflow-logs/               # Airflow logs
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ .env
└─ README.md
```

---

## 🚀 Getting Started

1. **Prepare persistent folders:**

   ```bash
   mkdir -p lake/bronze lake/silver lake/gold typesense-data dags airflow-logs
   ```
2. **Place CSV files in `lake/bronze/`**
   Example: `project.csv`, `organization.csv`, `topics.csv`, etc.
3. **Configure variables in `.env`**
   Include Supabase/Postgres and Typesense credentials.

   Example `.env`:

   ```
   SUPABASE_DB_URL=postgresql://user:password@host:5432/dbname
   TYPESENSE_API_KEY=your_typesense_api_key
   AIRFLOW_API_URL=http://localhost:8080/api/v1
   AIRFLOW_API_TOKEN=your_airflow_token
   ```
4. **Start the services:**

   ```bash
   docker compose up --build
   ```
5. **Access the services:**

   - **API:** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Airflow:** [http://localhost:8080](http://localhost:8080)
   - **Typesense:** [http://localhost:8108](http://localhost:8108)

---

## 🛠️ ETL and Vectorization

- **bronze_to_silver.py:** Cleans and normalizes raw Bronze data to Silver (Parquet).
- **silver_to_gold.py:** Models Silver data into a Gold star schema (Parquet).
- **sync_to_supabase.py:** Loads Gold tables into Supabase/Postgres for SQL queries and API.
- **index_projects_typesense.py:**
  Reads Gold projects, generates embeddings with a transformer model, and indexes them in Typesense for semantic and faceted search.

---

## ⚡ Orchestration (Airflow)

- **lakehouse_watch_any_file.py:**

  - Sensor detects changes in Bronze files.
  - Runs ETL only for modified files.
  - Vectorizes and indexes new projects in Typesense.
- **lakehouse_full_run.py:**

  - Runs the full pipeline (Bronze → Silver → Gold → Supabase).
  - Vectorizes and indexes all projects in Typesense.

---

## 🌐 REST API (FastAPI)

### Main Endpoints

- **`/seed`** `POST /seed` Triggers the `lakehouse_full_run` DAG via Airflow to run the full pipeline and vectorization.
- **`/raw`** CRUD for files in Bronze (upload, list, delete).
- **`/gold/projects`** Query projects in Gold/Supabase, filtering by country and year.
- **`/search`**

  - `POST /search/init` : Initializes the collection in Typesense.
  - `POST /search/index`: Indexes Gold projects in Typesense (includes embeddings).
  - `GET /search`       : Text and filter search (country, year, facets).

### Usage Example

```bash
# Trigger full pipeline
curl -u admin:supersecret -X POST http://localhost:8000/seed

# Initialize search collection
curl -u admin:supersecret -X POST http://localhost:8000/search/init

# Index projects in Typesense
curl -u admin:supersecret -X POST http://localhost:8000/search/index

# Search projects
curl -u admin:supersecret "http://localhost:8000/search?q=ai&country=DE&year=2023"
```

---

## 🧩 Advanced Configuration

- **Typesense persistence:** Use only the `typesense-data` folder as Docker volume. If you need to clear the index, you can delete the folder and restart the service.
- **Environment variables:** Adjust `.env` for your credentials and paths. You can change the API port, Airflow URL, etc.
- **Embeddings:** The `index_projects_typesense.py` script uses a transformer model (e.g. `sentence-transformers`) to generate vectors. You can change the model in the script as needed.
- **Airflow:**
  The `/seed` API triggers the `lakehouse_full_run` DAG using Airflow's REST API.
  Make sure Airflow has the API enabled and the DAG is in the `dags/` folder.

---

## ✅ Solution Checklist

- [X] Medallion Architecture (Bronze/Silver/Gold)
- [X] Modular and reproducible ETL
- [X] Relational data warehouse (Supabase/Postgres)
- [X] Gold star schema
- [X] REST API with basic authentication
- [X] Vector and faceted search in Typesense
- [X] Orchestration with Airflow (sensor + full pipeline)
- [X] Indexing with embeddings (transformer)
- [X] Docker Compose to launch the entire stack

---

## 💬 Final Notes

- The pipeline and architecture are easily migratable to cloud environments (Databricks, Delta Lake, etc.).
- You can extend vector search, add facets, or add endpoints as needed.
- Typesense persistence should be in the `typesense-data` folder (see `docker-compose.yml`).

---

## 🧭 Diagrams (Mermaid)

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
  SI -->|star modeling| GO[Gold (Parquet)]

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
    S1[project.parquet\n- normalized types\n- typed dates\n- duration_days]
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

## 📜 License

MIT (or your preferred license).