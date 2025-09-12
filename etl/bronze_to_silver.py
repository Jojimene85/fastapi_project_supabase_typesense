
"""
Bronze -> Silver (curated/clean, por dataset)
- Funciones finas por archivo para ejecutar sólo lo que cambió.
"""

from pathlib import Path
import pandas as pd
from common.paths import BRONZE_DIR, SILVER_DIR, GOLD_DIR, ensure_dirs

BRONZE = BRONZE_DIR
SILVER = SILVER_DIR
SILVER.mkdir(parents=True, exist_ok=True)

def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, sep=";", encoding="utf-8", on_bad_lines="skip")
    except Exception:
        try:
            return pd.read_csv(path, sep=",", encoding="utf-8", on_bad_lines="skip", engine="python")
        except Exception:
            return pd.DataFrame()

def _to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, errors="coerce", utc=False)

def _to_num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")

def _strip_unnamed(df: pd.DataFrame) -> pd.DataFrame:
    return df.loc[:, ~df.columns.str.startswith("Unnamed")].copy()

# ---------- datasets finos ----------

def run_projects_only():
    """project.csv -> silver/project.parquet (tipos/fechas/dedup)"""
    src = BRONZE / "project.csv"
    df = _safe_read_csv(src)
    if df.empty:
        print("[projects] no source")
        return
    df = _strip_unnamed(df)

    if "id" in df.columns and "projectID" not in df.columns:
        df = df.rename(columns={"id": "projectID"})

    if "keywords" in df.columns:
        df = df.loc[:, :"keywords"]

    for c in ("startDate", "endDate"):
        if c in df.columns:
            df[c] = _to_date(df[c])
    for c in ("totalCost", "ecMaxContribution"):
        if c in df.columns:
            df[c] = _to_num(df[c])

    if {"startDate", "endDate"}.issubset(df.columns):
        df["duration_days"] = (df["endDate"] - df["startDate"]).dt.days

    if "projectID" in df.columns:
        df = df.drop_duplicates(subset=["projectID"])
    else:
        df = df.drop_duplicates()

    out = SILVER / "project.parquet"
    df.to_parquet(out, index=False)
    print("OK silver/project.parquet")

def run_organizations_only():
    """organization.csv -> silver/organizations_info.parquet + organizations_project.parquet"""
    src = BRONZE / "organization.csv"
    df = _safe_read_csv(src)
    if df.empty:
        print("[organizations] no source")
        return
    df = _strip_unnamed(df)

    org_info_cols = [
        "organisationID","vatNumber","name","shortName",
        "street","postCode","city","country",
        "nutsCode","geolocation","organizationURL",
    ]
    info = df[[c for c in org_info_cols if c in df.columns]].copy()
    if not info.empty:
        if "country" in info.columns:
            info["country"] = info["country"].astype(str).str.strip()
        if "organisationID" in info.columns:
            info["organisationID"] = info["organisationID"].astype(str).str.strip()
        info = info.drop_duplicates()
        info.to_parquet(SILVER / "organizations_info.parquet", index=False)
        print("OK silver/organizations_info.parquet")

    # relación org-proyecto (¡conservar organisationID!)
    drop_cols = [c for c in org_info_cols if c in df.columns and c != "organisationID"]
    rel = df.drop(columns=drop_cols, errors="ignore").copy()

    if "projectId" in rel.columns and "projectID" not in rel.columns:
        rel = rel.rename(columns={"projectId": "projectID"})
    if "organisationID" in rel.columns:
        rel["organisationID"] = rel["organisationID"].astype(str).str.strip()

    for c in ("ecContribution", "netEcContribution", "totalCost"):
        if c in rel.columns:
            rel[c] = _to_num(rel[c])

    rel = rel.drop_duplicates()
    rel.to_parquet(SILVER / "organizations_project.parquet", index=False)
    print("OK silver/organizations_project.parquet")

def run_topics_only():
    """topics.csv -> silver/topics.parquet (passthrough robusto)"""
    src = BRONZE / "topics.csv"
    df = _safe_read_csv(src)
    if df.empty:
        print("[topics] no source")
        return
    df = _strip_unnamed(df)
    df.to_parquet(SILVER / "topics.parquet", index=False)
    print("OK silver/topics.parquet")

def run_legalbasis_only():
    """legalBasis.csv -> silver/legalBasis.parquet (passthrough robusto)"""
    src = BRONZE / "legalBasis.csv"
    df = _safe_read_csv(src)
    if df.empty:
        print("[legalBasis] no source")
        return
    df = _strip_unnamed(df)
    df.to_parquet(SILVER / "legalBasis.parquet", index=False)
    print("OK silver/legalBasis.parquet")

def run_passthrough(name: str):
    """Copia un CSV cualquiera de bronze a silver con el mismo nombre base."""
    src = BRONZE / f"{name}.csv"
    df = _safe_read_csv(src)
    if df.empty:
        print(f"[{name}] no source")
        return
    df = _strip_unnamed(df)
    df.to_parquet(SILVER / f"{name}.parquet", index=False)
    print(f"OK silver/{name}.parquet")

# ---------- entrypoints ----------

FILE_TO_FUNC = {
    "project.csv": run_projects_only,
    "organization.csv": run_organizations_only,
    "topics.csv": run_topics_only,
    "legalBasis.csv": run_legalbasis_only,
    # si querés: policyPriorities/euroSciVoc/webItem/webLink como passthrough
    "policyPriorities.csv": lambda: run_passthrough("policyPriorities"),
    "euroSciVoc.csv":       lambda: run_passthrough("euroSciVoc"),
    "webItem.csv":          lambda: run_passthrough("webItem"),
    "webLink.csv":          lambda: run_passthrough("webLink"),
}

def run_files(changed_files: set[str]):
    """Ejecuta sólo los datasets cuyos CSV cambiaron."""
    for f in changed_files:
        func = FILE_TO_FUNC.get(f)
        if func:
            func()
        else:
            print(f"[WARN] sin handler para {f}")

def run():
    """Full (por compatibilidad)."""
    for func in FILE_TO_FUNC.values():
        func()

