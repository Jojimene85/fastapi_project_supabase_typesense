# etl/silver_to_gold.py
"""
Silver -> Gold
- Builders por cada tabla de la capa Gold (dimensiones, bridges y fact).
- Entrypoints:
    - run()                : full refresh (en orden de dependencias).
    - run(only=[...])      : selectivo por nombres de tablas Gold.
    - run_targets([...])   : alias compatible con orquestación selectiva.
    - run_for_sources([...]): mapea CSVs cambiados -> tablas Gold a regenerar.
"""

from __future__ import annotations
from typing import Iterable
from pathlib import Path
import pandas as pd

from common.paths import SILVER_DIR, GOLD_DIR

SILVER: Path = SILVER_DIR
GOLD: Path = GOLD_DIR
GOLD.mkdir(parents=True, exist_ok=True)

# ---------- helpers ----------

def _read(name: str) -> pd.DataFrame:
    """Lee un parquet de Silver de forma segura."""
    path = SILVER / f"{name}.parquet"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def _norm_project_id_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columna de project id: projectID (string limpia)."""
    d = df.copy()
    if "id" in d.columns and "projectID" not in d.columns:
        d = d.rename(columns={"id": "projectID"})
    if "projectId" in d.columns and "projectID" not in d.columns:
        d = d.rename(columns={"projectId": "projectID"})
    if "projectID" in d.columns:
        d["projectID"] = d["projectID"].astype(str).str.strip()
    return d

# ---------- builders ----------

def build_dim_project():
    p = _read("project")
    if p.empty:
        print("[dim_project] no source")
        return
    d = p.copy()

    # columnas típicas presentes en silver/project.parquet
    # duration_days ya viene calculado en bronze_to_silver
    # asegurar tipos básicos
    for c in ("startDate", "endDate"):
        if c in d.columns:
            d[c] = pd.to_datetime(d[c], errors="coerce")

    # derivado de fechas si year no está
    if "year" not in d.columns:
        if "startDate" in d.columns:
            d["year"] = d["startDate"].dt.year.astype("Int64")
        else:
            d["year"] = pd.Series([pd.NA] * len(d), dtype="Int64")

    # ordenar columnas “core” si existen
    cols = [
        "projectID", "acronym", "title", "abstract", "startDate", "endDate",
        "duration_days", "totalCost", "ecMaxContribution", "country", "status", "year"
    ]
    keep = [c for c in cols if c in d.columns]
    d = d[keep].drop_duplicates()

    d.to_parquet(GOLD / "dim_project.parquet", index=False)
    print("OK gold/dim_project.parquet")

def build_dim_organization():
    info = _read("organizations_info")
    rel  = _read("organizations_project")
    if info.empty and rel.empty:
        print("[dim_organization] no source")
        return

    # surrogate key por organización (hash estable por organisationID si existe)
    if not info.empty:
        base = info.copy()
    else:
        base = rel[["organisationID"]].drop_duplicates()

    if "organisationID" in base.columns:
        base["organisationID"] = base["organisationID"].astype(str).str.strip()
    base = base.drop_duplicates()

    # surrogate key (ordinal estable)
    base = base.reset_index(drop=True)
    base["org_sk"] = base.index + 1

    # country puede venir en info
    if "country" not in base.columns and "country" in info.columns:
        base = base.merge(info[["organisationID","country"]].drop_duplicates(), on="organisationID", how="left")

    # columnas de salida
    out_cols = ["org_sk","organisationID","name","shortName","country","vatNumber","street","postCode","city","organizationURL","nutsCode","geolocation"]
    have = [c for c in out_cols if c in base.columns]
    d = base[["org_sk"] + [c for c in have if c != "org_sk"]].drop_duplicates()

    d.to_parquet(GOLD / "dim_organization.parquet", index=False)
    print("OK gold/dim_organization.parquet")

def build_fact_funding():
    rel  = _read("organizations_project")
    dorg = pd.read_parquet(GOLD / "dim_organization.parquet") if (GOLD / "dim_organization.parquet").exists() else pd.DataFrame()
    if rel.empty or dorg.empty:
        print("[fact_funding] no source")
        return

    df = rel.copy()
    # normalizar projectID
    df = _norm_project_id_cols(df)
    # join surrogate key
    df = df.merge(dorg[["org_sk","organisationID"]], on="organisationID", how="left")

    # métricas numéricas (si existen)
    metrics = []
    for c in ("ecContribution","netEcContribution","totalCost"):
        if c in df.columns:
            metrics.append(c)

    keep = ["projectID","org_sk"] + metrics
    keep = [c for c in keep if c in df.columns]
    f = df[keep].dropna(subset=["projectID","org_sk"]).drop_duplicates()

    # derivar year si existe startDate en dim_project
    dp = pd.read_parquet(GOLD / "dim_project.parquet") if (GOLD / "dim_project.parquet").exists() else pd.DataFrame()
    if not dp.empty and {"projectID","year"}.issubset(dp.columns):
        f = f.merge(dp[["projectID","year"]], on="projectID", how="left")

    f.to_parquet(GOLD / "fact_funding.parquet", index=False)
    print("OK gold/fact_funding.parquet")

def build_dim_time():
    dp = pd.read_parquet(GOLD / "dim_project.parquet") if (GOLD / "dim_project.parquet").exists() else pd.DataFrame()
    if dp.empty or "startDate" not in dp.columns:
        print("[dim_time] no source")
        return

    dates = pd.concat([dp["startDate"], dp["endDate"]], ignore_index=True)
    dates = pd.to_datetime(dates, errors="coerce").dropna().drop_duplicates()
    if dates.empty:
        print("[dim_time] no dates")
        return

    t = pd.DataFrame({"date": dates.sort_values().reset_index(drop=True)})
    t["date_key"]  = t["date"].dt.strftime("%Y%m%d").astype(int)
    t["year"]      = t["date"].dt.year
    t["quarter"]   = t["date"].dt.quarter
    t["month"]     = t["date"].dt.month
    t["month_name"]= t["date"].dt.month_name()
    t["week"]      = t["date"].dt.isocalendar().week.astype(int)
    t["dow"]       = t["date"].dt.weekday + 1
    t.to_parquet(GOLD / "dim_time.parquet", index=False)
    print("OK gold/dim_time.parquet")

def build_dim_country():
    do = pd.read_parquet(GOLD / "dim_organization.parquet") if (GOLD / "dim_organization.parquet").exists() else pd.DataFrame()
    if do.empty or "country" not in do.columns:
        print("[dim_country] no source")
        return
    d = (
        do[["country"]].dropna().drop_duplicates()
        .assign(country_key=lambda x: x["country"].astype(str).str.upper().str.replace(r"\s+","_", regex=True))
    )
    d = d[["country_key","country"]]
    d.to_parquet(GOLD / "dim_country.parquet", index=False)
    print("OK gold/dim_country.parquet")

def build_dim_topic_and_bridge():
    tp = _read("topics")
    if tp.empty:
        print("[dim_topic/bridge] no source")
        return
    tp = _norm_project_id_cols(tp)
    if "projectID" not in tp.columns:
        return

    code_col  = next((c for c in ["topicCode","topic","code","id"] if c in tp.columns), None)
    label_col = next((c for c in ["topicName","name","title","label","description"] if c in tp.columns), None)
    if not code_col:
        return

    dim_topic = tp[[code_col] + ([label_col] if label_col else [])].drop_duplicates()
    dim_topic = dim_topic.rename(columns={code_col: "topic_code"})
    if label_col:
        dim_topic = dim_topic.rename(columns={label_col: "topic_name"})
    dim_topic["topic_id"] = pd.factorize(dim_topic["topic_code"])[0] + 1
    dim_topic = dim_topic[["topic_id","topic_code"] + (["topic_name"] if "topic_name" in dim_topic.columns else [])]
    dim_topic.to_parquet(GOLD / "dim_topic.parquet", index=False)

    bpt = tp[["projectID", code_col]].dropna().drop_duplicates().rename(columns={code_col: "topic_code"})
    bpt = bpt.merge(dim_topic[["topic_id","topic_code"]], on="topic_code", how="left")[["projectID","topic_id"]]
    bpt = bpt.dropna().drop_duplicates()
    bpt.to_parquet(GOLD / "bridge_project_topic.parquet", index=False)
    print("OK gold/dim_topic.parquet / bridge_project_topic.parquet")

def build_dim_program_and_bridge():
    lb = _read("legalBasis")
    if lb.empty:
        print("[dim_program/bridge] no source")
        return
    lb = _norm_project_id_cols(lb)
    if "projectID" not in lb.columns:
        return

    code_col  = next((c for c in ["legalBasis","code","id"] if c in lb.columns), None)
    label_col = next((c for c in ["name","title","label","description"] if c in lb.columns), None)
    if not code_col:
        return

    dim_program = lb[[code_col] + ([label_col] if label_col else [])].drop_duplicates()
    dim_program = dim_program.rename(columns={code_col: "program_code"})
    if label_col:
        dim_program = dim_program.rename(columns={label_col: "program_name"})
    dim_program["program_id"] = pd.factorize(dim_program["program_code"])[0] + 1
    dim_program = dim_program[["program_id","program_code"] + (["program_name"] if "program_name" in dim_program.columns else [])]
    dim_program.to_parquet(GOLD / "dim_program.parquet", index=False)

    bpp = lb[["projectID", code_col]].dropna().drop_duplicates().rename(columns={code_col: "program_code"})
    bpp = bpp.merge(dim_program[["program_id","program_code"]], on="program_code", how="left")[["projectID","program_id"]]
    bpp = bpp.dropna().drop_duplicates()
    bpp.to_parquet(GOLD / "bridge_project_program.parquet", index=False)
    print("OK gold/dim_program.parquet / bridge_project_program.parquet")

def build_status_and_bridge():
    dp = pd.read_parquet(GOLD / "dim_project.parquet") if (GOLD / "dim_project.parquet").exists() else pd.DataFrame()
    if dp.empty or "status" not in dp.columns:
        print("[dim_status/bridge] no source")
        return
    ds = (dp[["status"]].dropna().drop_duplicates()
          .assign(status_id=lambda d: pd.factorize(d["status"])[0] + 1))
    if ds.empty:
        return
    ds = ds.rename(columns={"status": "status_name"})
    ds.to_parquet(GOLD / "dim_status.parquet", index=False)

    bps = (
        dp[["projectID","status"]]
        .merge(ds.rename(columns={"status_name": "status"}), on="status", how="left")
        [["projectID","status_id"]]
        .drop_duplicates()
    )
    bps.to_parquet(GOLD / "bridge_project_status.parquet", index=False)
    print("OK gold/dim_status.parquet / bridge_project_status.parquet")

# ---------- entrypoints selectivos ----------

TABLE_BUILDERS = {
    "dim_project": build_dim_project,
    "dim_organization": build_dim_organization,
    "fact_funding": build_fact_funding,
    "dim_time": build_dim_time,
    "dim_country": build_dim_country,
    "dim_topic": build_dim_topic_and_bridge,      # también escribe bridge_project_topic
    "bridge_project_topic": build_dim_topic_and_bridge,
    "dim_program": build_dim_program_and_bridge,  # también escribe bridge_project_program
    "bridge_project_program": build_dim_program_and_bridge,
    "dim_status": build_status_and_bridge,
    "bridge_project_status": build_status_and_bridge,
}

# qué tablas gold dependen de cada fuente (csv)
SOURCE_TO_GOLD = {
    "project.csv":      ["dim_project","dim_time","dim_status"],
    "organization.csv": ["dim_organization","dim_country","fact_funding"],
    "topics.csv":       ["dim_topic","bridge_project_topic"],
    "legalBasis.csv":   ["dim_program","bridge_project_program"],
    "policyPriorities.csv": [],  # agrega si modelás
    "euroSciVoc.csv":       [],
    "webItem.csv":          [],
    "webLink.csv":          [],
}

def run(only: Iterable[str] | None = None):
    """Ejecuta builders por nombre de tabla Gold. Si None, ejecuta todo."""
    targets = list(only) if only else list(TABLE_BUILDERS.keys())
    # Orden mínimo por dependencias
    order = [
        "dim_project",
        "dim_organization",
        "fact_funding",
        "dim_time",
        "dim_country",
        "dim_program", "bridge_project_program",
        "dim_topic",   "bridge_project_topic",
        "dim_status",  "bridge_project_status",
    ]
    seen: set[str] = set()
    for t in order:
        if t in targets and t not in seen:
            TABLE_BUILDERS[t]()
            seen.add(t)
    # cualquier otro target no listado en order
    for t in targets:
        if t not in seen and t in TABLE_BUILDERS:
            TABLE_BUILDERS[t]()

def run_targets(targets: Iterable[str]):
    """Alias requerido por la orquestación selectiva (Airflow)."""
    return run(only=targets)

def run_for_sources(sources: Iterable[str]):
    """Resuelve tablas Gold a partir de las fuentes cambiadas y ejecuta sólo esas."""
    gold_targets: set[str] = set()
    for s in sources:
        gold_targets.update(SOURCE_TO_GOLD.get(s, []))
    return run(only=gold_targets)

