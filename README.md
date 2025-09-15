
# Lakehouse (pandas) – EU Research Projects

> Arquitectura Lakehouse con **pandas + Parquet**, **Supabase (Postgres)** como DWH, **Typesense** para búsqueda vectorial y **FastAPI** como API.
> Orquestación con **Airflow** (sensores de archivos y pipeline completo).
> Incluye indexación de proyectos con embeddings (vectorización) generados mediante una función en Supabase para búsqueda semántica.
> Testing automatizado para aseguramiento de calidad.

---

## 🧭 Arquitectura General

- **Data Lake local (filesystem)**
  - `lake/bronze/` → archivos crudos (CSV)
  - `lake/silver/` → datos limpios/normalizados (Parquet)
  - `lake/gold/` → modelo estrella (Parquet)
- **ETL modular (Python + pandas)**
  - Limpieza, normalización, modelado y carga en Supabase/Postgres
  - Indexación en Typesense con embeddings (vectorización)
- **Orquestación**
  - Airflow con dos DAGs:
    - `lakehouse_watch_any_file.py`: ejecuta ETL selectivo al detectar cambios en Bronze
    - `lakehouse_full_run.py`: ejecuta el pipeline completo + vectorización
- **API REST (FastAPI)**
  - Endpoints para consulta, búsqueda, disparo del pipeline (seed) y CRUD de archivos
  - Búsqueda avanzada por texto y facetas usando Typesense
- **Testing**
  - Tests automáticos para verificar la correcta operación de los ETL, endpoints y búsqueda.

---

## 🛠️ Tecnologías utilizadas

- **Python 3.10+** – Lenguaje principal de programación
- **Pandas** – Manipulación de datos y ETL
- **FastAPI** – Framework para APIs RESTful
- **Supabase (Postgres)** – Base de datos en la nube y hosting
- **Typesense** – Motor de búsqueda vectorial y facetada
- **Docker & Docker Compose** – Contenerización y orquestación
- **Apache Airflow** – Orquestación de flujos de trabajo (DAGs, sensores)
- **Pytest** – Testing automatizado
- **SQLAlchemy** – ORM e interacción con la base de datos
- **Parquet** – Formato de almacenamiento columnar para Silver/Gold
- **Mermaid** – Diagramas de arquitectura en markdown

---

## 🧩 Estructura del Proyecto

```
.
├─ api/                        # FastAPI: endpoints REST, autenticación, servicios
│  ├─ main.py
│  ├─ auth.py
│  ├─ routes/
│  │  ├─ seed.py               # /seed → dispara pipeline completo vía Airflow
│  │  ├─ raw.py                # /raw → CRUD en Bronze
│  │  ├─ gold.py               # /gold → queries en Gold/Supabase
│  │  └─ search.py             # /search → init, index, query en Typesense
│  ├─ services/
│  │  ├─ db.py                 # Conexión SQLAlchemy a Supabase/Postgres
│  │  ├─ typesense_client.py   # Cliente Typesense
│  │  └─ embeddings.py         # Lógica de embeddings (integración función Supabase)
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
├─ tests/                      # Tests automáticos (Pytest)
├─ Dockerfile
├─ docker-compose.yml
├─ requirements.txt
├─ .env
└─ README.md
```

---

## 🚀 Puesta en marcha

**Toda la operación se realiza levantando el stack con Docker Compose.**

### 1. Prepara carpetas persistentes

```bash
mkdir -p lake/bronze lake/silver lake/gold typesense-data dags airflow-logs
```

### 2. Coloca los archivos CSV en `lake/bronze/`

Ejemplo: `project.csv`, `organization.csv`, `topics.csv`, etc.

### 3. Configura variables en `.env`

Incluye credenciales de Supabase/Postgres, Typesense y Airflow.

Ejemplo de `.env`:

```
SUPABASE_DB_URL=postgresql://user:password@host:5432/dbname
TYPESENSE_API_KEY=your_typesense_api_key
AIRFLOW_API_URL=http://localhost:8080/api/v1
AIRFLOW_API_TOKEN=your_airflow_token
```

### 4. Levanta el stack completo

```bash
docker compose up --build
```

Esto inicia todos los servicios: API, Airflow, Typesense, base de datos, etc.
Puedes operar ETL, búsquedas, testing, todo desde los servicios Docker.

### 5. Accede a los servicios

- **API:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Airflow:** [http://localhost:8080](http://localhost:8080)
- **Typesense:** [http://localhost:8108](http://localhost:8108)

### 6. Ejecuta los tests

```bash
docker compose exec api pytest tests/
```

---

## 🛠️ ETL, Embeddings y Vectorización

- **bronze_to_silver.py:** Limpia y normaliza los datos crudos de Bronze a Silver (Parquet).
- **silver_to_gold.py:** Modela los datos Silver en un esquema estrella Gold (Parquet).
- **sync_to_supabase.py:** Carga las tablas Gold en Supabase/Postgres para consultas SQL y API.
- **Embeddings en Supabase:**Los embeddings se generan usando una función definida en Supabase, directamente sobre los registros Gold. La lógica está implementada en `api/services/embeddings.py`.
- **index_projects_typesense.py:**
  Lee los embeddings y proyectos Gold desde Supabase y los indexa en Typesense para búsqueda semántica y facetada.

---

## ⚡ Orquestación (Airflow)

- **lakehouse_watch_any_file.py:**
  - Sensor detecta cambios en archivos Bronze.
  - Ejecuta ETL solo para los archivos modificados.
  - Vectoriza e indexa proyectos nuevos en Typesense.
- **lakehouse_full_run.py:**
  - Ejecuta el pipeline completo (Bronze → Silver → Gold → Supabase).
  - Genera embeddings en Supabase y los indexa en Typesense.

---

## 🌐 API REST (FastAPI)

### Endpoints principales

- **`/seed`**`POST /seed` Dispara el DAG `lakehouse_full_run` vía Airflow para ejecutar el pipeline completo y vectorización.
- **`/raw`**CRUD de archivos en Bronze (subida, listado, borrado).
- **`/gold/projects`**Consulta proyectos en Gold/Supabase, filtrando por país y año.
- **`/search`**
  - `POST /search/init` : Inicializa la colección en Typesense.
  - `POST /search/index`: Indexa proyectos Gold en Typesense (incluye embeddings desde Supabase).
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

## 🧪 Testing

- **Cobertura:**Los tests cubren los siguientes aspectos:
  - Funcionamiento de los ETL.
  - Validación de endpoints de la API.
  - Integridad y precisión de búsquedas en Typesense.
- **Herramienta:**
  Se utiliza `pytest` y pueden ejecutarse con:
  ```bash
  docker compose exec api pytest tests/
  ```

---

## ✅ Checklist de la Solución

- [X] Arquitectura Medallion (Bronze/Silver/Gold)
- [X] ETL modular y reproducible
- [X] Data warehouse relacional (Supabase/Postgres)
- [X] Modelo estrella en Gold
- [X] API REST con autenticación básica
- [X] Búsqueda vectorial y facetada en Typesense
- [X] Orquestación con Airflow (sensor + pipeline completo)
- [X] Indexación con embeddings (función en Supabase, ver `embeddings.py`)
- [X] Módulo de testing automatizado
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

  GO -->|carga y embeddings (función en Supabase)| DB[(Supabase / Postgres)]
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

## 🤝 Contribución

¡Las contribuciones son bienvenidas!
Por favor, abre un issue o un pull request para sugerencias, mejoras o correcciones.
Para reportar bugs, utiliza el módulo de testing y adjunta resultados.

---

## 📜 Licencia

MIT

<style>#mermaid-1757921586946{font-family:sans-serif;font-size:16px;fill:#333;}#mermaid-1757921586946 .error-icon{fill:#552222;}#mermaid-1757921586946 .error-text{fill:#552222;stroke:#552222;}#mermaid-1757921586946 .edge-thickness-normal{stroke-width:2px;}#mermaid-1757921586946 .edge-thickness-thick{stroke-width:3.5px;}#mermaid-1757921586946 .edge-pattern-solid{stroke-dasharray:0;}#mermaid-1757921586946 .edge-pattern-dashed{stroke-dasharray:3;}#mermaid-1757921586946 .edge-pattern-dotted{stroke-dasharray:2;}#mermaid-1757921586946 .marker{fill:#333333;}#mermaid-1757921586946 .marker.cross{stroke:#333333;}#mermaid-1757921586946 svg{font-family:sans-serif;font-size:16px;}#mermaid-1757921586946 .label{font-family:sans-serif;color:#333;}#mermaid-1757921586946 .label text{fill:#333;}#mermaid-1757921586946 .node rect,#mermaid-1757921586946 .node circle,#mermaid-1757921586946 .node ellipse,#mermaid-1757921586946 .node polygon,#mermaid-1757921586946 .node path{fill:#ECECFF;stroke:#9370DB;stroke-width:1px;}#mermaid-1757921586946 .node .label{text-align:center;}#mermaid-1757921586946 .node.clickable{cursor:pointer;}#mermaid-1757921586946 .arrowheadPath{fill:#333333;}#mermaid-1757921586946 .edgePath .path{stroke:#333333;stroke-width:1.5px;}#mermaid-1757921586946 .flowchart-link{stroke:#333333;fill:none;}#mermaid-1757921586946 .edgeLabel{background-color:#e8e8e8;text-align:center;}#mermaid-1757921586946 .edgeLabel rect{opacity:0.5;background-color:#e8e8e8;fill:#e8e8e8;}#mermaid-1757921586946 .cluster rect{fill:#ffffde;stroke:#aaaa33;stroke-width:1px;}#mermaid-1757921586946 .cluster text{fill:#333;}#mermaid-1757921586946 div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:sans-serif;font-size:12px;background:hsl(80,100%,96.2745098039%);border:1px solid #aaaa33;border-radius:2px;pointer-events:none;z-index:100;}#mermaid-1757921586946:root{--mermaid-font-family:sans-serif;}#mermaid-1757921586946:root{--mermaid-alt-font-family:sans-serif;}#mermaid-1757921586946 flowchart-v2{fill:apa;}</style>
