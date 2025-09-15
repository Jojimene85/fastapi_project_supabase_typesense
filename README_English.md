
# Lakehouse (pandas) – EU Research Projects

> Lakehouse architecture with **pandas + Parquet**, **Supabase (Postgres)** as DWH, **Typesense** for vector search, and **FastAPI** for API exposure.
> Orchestration via **Airflow** (file sensors and full pipeline).
> Includes indexing of projects with embeddings (vectorization) generated through a Supabase function for semantic search.
> Automated testing for quality assurance.

---

## 🧭 General Architecture

- **Local Data Lake (filesystem)**
  - `lake/bronze/` → raw files (CSV)
  - `lake/silver/` → cleaned/normalized data (Parquet)
  - `lake/gold/` → star schema model (Parquet)
- **Modular ETL (Python + pandas)**
  - Cleansing, normalization, modeling, and loading to Supabase/Postgres
  - Indexing in Typesense with embeddings (vectorization)
- **Orchestration**
  - Airflow with two DAGs:
    - `lakehouse_watch_any_file.py`: runs selective ETL upon detecting changes in Bronze
    - `lakehouse_full_run.py`: runs full pipeline + vectorization
- **REST API (FastAPI)**
  - Endpoints for querying, searching, pipeline trigger (seed), and file CRUD
  - Advanced search by text and facets using Typesense
- **Testing**
  - Automated tests to verify ETLs, endpoints, and search functionality

---

## 🛠️ Technologies Used

- **Python 3.10+** – Main programming language
- **Pandas** – Data manipulation and ETL
- **FastAPI** – RESTful API framework
- **Supabase (Postgres)** – Cloud database and hosting
- **Typesense** – Vector and faceted search engine
- **Docker & Docker Compose** – Containerization and orchestration
- **Apache Airflow** – Workflow orchestration (DAGs, sensors)
- **Pytest** – Automated testing
- **SQLAlchemy** – ORM and database interaction
- **Parquet** – Columnar storage format for Silver/Gold layers
- **Mermaid** – Architecture diagrams in markdown

---

## 🧩 Project Structure

```
.
├─ api/                        # FastAPI: REST endpoints, authentication, services
│  ├─ main.py
│  ├─ auth.py
│  ├─ routes/
│  │  ├─ seed.py               # /seed → triggers full pipeline via Airflow
│  │  ├─ raw.py                # /raw → CRUD on Bronze
│  │  ├─ gold.py               # /gold → queries on Gold/Supabase
│  │  └─ search.py             # /search → init, index, query in Typesense
│  ├─ services/
│  │  ├─ db.py                 # SQLAlchemy connection to Supabase/Postgres
│  │  ├─ typesense_client.py   # Typesense client
│  │  └─ embeddings.py         # Embeddings logic (Supabase function integration)
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
│  ├─ lakehouse_watch_any_file.py # DAG: Bronze file change sensor + selective ETL + vectorization
│  └─ lakehouse_full_run.py       # DAG: full pipeline + vectorization
│
├─ lake/
│  ├─ bronze/                  # Raw files
│  ├─ silver/                  # Normalized Parquet
│  └─ gold/                    # Parquet star schema
│
├─ typesense-data/             # Typesense persistence (Docker volume)
├─ airflow-logs/               # Airflow logs
├─ tests/                      # Automated tests (Pytest)
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ .env
└─ README.md
```

---

## 🚀 Getting Started

**All operations are performed by launching the stack with Docker Compose.**

### 1. Prepare persistent folders

```bash
mkdir -p lake/bronze lake/silver lake/gold typesense-data dags airflow-logs
```

### 2. Place your CSV files in `lake/bronze/`

E.g.: `project.csv`, `organization.csv`, `topics.csv`, etc.

### 3. Configure your `.env` file

Include credentials for Supabase/Postgres, Typesense, and Airflow.

Example `.env`:

```
SUPABASE_DB_URL=postgresql://user:password@host:5432/dbname
TYPESENSE_API_KEY=your_typesense_api_key
AIRFLOW_API_URL=http://localhost:8080/api/v1
AIRFLOW_API_TOKEN=your_airflow_token
```

### 4. Launch the full stack

```bash
docker compose up --build
```

This starts all services: API, Airflow, Typesense, database, etc.
All ETL, search, and testing operations run inside Docker services.

### 5. Access the services

- **API:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Airflow:** [http://localhost:8080](http://localhost:8080)
- **Typesense:** [http://localhost:8108](http://localhost:8108)

### 6. Run the tests

```bash
docker compose exec api pytest tests/
```

---

## 🛠️ ETL, Embeddings & Vectorization

- **bronze_to_silver.py:** Cleans and normalizes Bronze raw data to Silver (Parquet).
- **silver_to_gold.py:** Models Silver data into Gold star schema (Parquet).
- **sync_to_supabase.py:** Loads Gold tables into Supabase/Postgres for SQL queries and API.
- **Embeddings in Supabase:**Embeddings are generated using a function defined in Supabase, directly over Gold records. Logic is implemented in `api/services/embeddings.py`.
- **index_projects_typesense.py:**
  Reads embeddings and Gold projects from Supabase and indexes them in Typesense for semantic and faceted search.

---

## ⚡ Orchestration (Airflow)

- **lakehouse_watch_any_file.py:**
  - Sensor detects changes in Bronze files.
  - Runs ETL only for modified files.
  - Vectorizes and indexes new projects in Typesense.
- **lakehouse_full_run.py:**
  - Runs the complete pipeline (Bronze → Silver → Gold → Supabase).
  - Generates embeddings in Supabase and indexes them in Typesense.

---

## 🌐 REST API (FastAPI)

### Main Endpoints

- **`/seed`**`POST /seed` Triggers `lakehouse_full_run` DAG via Airflow for full pipeline and vectorization.
- **`/raw`**CRUD for Bronze files (upload, list, delete).
- **`/gold/projects`**Query Gold/Supabase projects, filter by country and year.
- **`/search`**
  - `POST /search/init` : Initialize Typesense collection.
  - `POST /search/index`: Index Gold projects into Typesense (includes embeddings from Supabase).
  - `GET /search`       : Search by text and filters (country, year, facets).

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

## 🧪 Testing

- **Coverage:**Tests cover:
  - ETL functionality
  - API endpoint validation
  - Search accuracy and integrity in Typesense
- **Tool:**
  Uses `pytest`, run with:
  ```bash
  docker compose exec api pytest tests/
  ```

---

## ✅ Solution Checklist

- [X] Medallion Architecture (Bronze/Silver/Gold)
- [X] Modular and reproducible ETL
- [X] Relational data warehouse (Supabase/Postgres)
- [X] Star schema in Gold
- [X] REST API with basic authentication
- [X] Vector and faceted search in Typesense
- [X] Orchestration with Airflow (sensor + full pipeline)
- [X] Embedding indexing (Supabase function, see `embeddings.py`)
- [X] Automated testing module
- [X] Docker Compose for full stack launch

---

## 💬 Final Notes

- Pipeline and architecture are easily migratable to cloud environments (Databricks, Delta Lake, etc.).
- You can extend vector search, add facets, or endpoints as needed.
- Typesense persistence must be in the `typesense-data` folder (see `docker-compose.yml`).

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

  GO -->|load & embeddings (Supabase function)| DB[(Supabase / Postgres)]
  DB -->|index docs| VS[(Typesense)]

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

## 🤝 Contribution

Contributions are welcome!
Please open an issue or pull request for suggestions, improvements, or fixes.
For bug reports, use the testing module and attach results.

---

## 📜 License

MIT (or your preferred license).

<style>#mermaid-1757921886881{font-family:sans-serif;font-size:16px;fill:#333;}#mermaid-1757921886881 .error-icon{fill:#552222;}#mermaid-1757921886881 .error-text{fill:#552222;stroke:#552222;}#mermaid-1757921886881 .edge-thickness-normal{stroke-width:2px;}#mermaid-1757921886881 .edge-thickness-thick{stroke-width:3.5px;}#mermaid-1757921886881 .edge-pattern-solid{stroke-dasharray:0;}#mermaid-1757921886881 .edge-pattern-dashed{stroke-dasharray:3;}#mermaid-1757921886881 .edge-pattern-dotted{stroke-dasharray:2;}#mermaid-1757921886881 .marker{fill:#333333;}#mermaid-1757921886881 .marker.cross{stroke:#333333;}#mermaid-1757921886881 svg{font-family:sans-serif;font-size:16px;}#mermaid-1757921886881 .label{font-family:sans-serif;color:#333;}#mermaid-1757921886881 .label text{fill:#333;}#mermaid-1757921886881 .node rect,#mermaid-1757921886881 .node circle,#mermaid-1757921886881 .node ellipse,#mermaid-1757921886881 .node polygon,#mermaid-1757921886881 .node path{fill:#ECECFF;stroke:#9370DB;stroke-width:1px;}#mermaid-1757921886881 .node .label{text-align:center;}#mermaid-1757921886881 .node.clickable{cursor:pointer;}#mermaid-1757921886881 .arrowheadPath{fill:#333333;}#mermaid-1757921886881 .edgePath .path{stroke:#333333;stroke-width:1.5px;}#mermaid-1757921886881 .flowchart-link{stroke:#333333;fill:none;}#mermaid-1757921886881 .edgeLabel{background-color:#e8e8e8;text-align:center;}#mermaid-1757921886881 .edgeLabel rect{opacity:0.5;background-color:#e8e8e8;fill:#e8e8e8;}#mermaid-1757921886881 .cluster rect{fill:#ffffde;stroke:#aaaa33;stroke-width:1px;}#mermaid-1757921886881 .cluster text{fill:#333;}#mermaid-1757921886881 div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:sans-serif;font-size:12px;background:hsl(80,100%,96.2745098039%);border:1px solid #aaaa33;border-radius:2px;pointer-events:none;z-index:100;}#mermaid-1757921886881:root{--mermaid-font-family:sans-serif;}#mermaid-1757921886881:root{--mermaid-alt-font-family:sans-serif;}#mermaid-1757921886881 flowchart-v2{fill:apa;}</style>
