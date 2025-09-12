"""
/gold: endpoints de consulta a la capa Gold (vía Supabase/Postgres).
GET /gold/projects?country=AR&year=2023
"""
from fastapi import APIRouter, Depends, Query
from api.auth import basic_auth
from api.services.db import get_engine
import pandas as pd

router = APIRouter(prefix="/gold", tags=["gold"])

@router.get(
    "/projects",
    dependencies=[Depends(basic_auth)],
)
def get_projects(
    country: str | None = Query(
        default=None,
        description="Esta API espera el país en formato ISO-2 (dos letras). Ejemplo: Argentina → AR. No distingue mayúsculas/minúsculas."
    ),
    year: int | None = Query(
        default=None,
        description="Año del proyecto (p. ej., 2023)."
    )
):
    """
    Devuelve proyectos con programa y países (agregados).
    - country: ISO-2 (ej. AR). Se normaliza a mayúsculas si viene en minúsculas.
    - year: filtra por p."year" de dim_project.
    """
    engine = get_engine()

    # Normaliza country a ISO-2 en mayúsculas si viene en minúsculas
    normalized_country = country.strip().upper() if country else None

    sql = """
    WITH base AS (
      SELECT
        p."projectID"                         AS project_id,
        p.title                               AS title,
        p."year"                              AS year,
        prog.program_code                     AS program,
        o.country                             AS country
      FROM dim_project p
      LEFT JOIN bridge_project_program bpp
        ON p."projectID" = bpp."projectID"
      LEFT JOIN dim_program prog
        ON bpp.program_id = prog.program_id
      LEFT JOIN fact_funding ff
        ON p."projectID" = ff."projectID"
      LEFT JOIN dim_organization o
        ON ff.org_sk = o.org_sk
      WHERE 1=1
        {country_filter}
        {year_filter}
    )
    SELECT
      project_id, title, program, year,
      ARRAY_REMOVE(ARRAY_AGG(DISTINCT country), NULL) AS countries
    FROM base
    GROUP BY project_id, title, program, year
    ORDER BY year DESC NULLS LAST, project_id
    LIMIT 1000
    """

    params = {}
    country_filter = ""
    year_filter = ""
    if normalized_country:
        country_filter = "AND o.country = %(country)s"
        params["country"] = normalized_country  # usa AR aunque envíen 'ar'
    if year is not None:
        year_filter = "AND p.\"year\" = %(year)s"
        params["year"] = year

    sql = sql.format(country_filter=country_filter, year_filter=year_filter)
    df = pd.read_sql(sql, engine, params=params)
    return {"count": len(df), "items": df.to_dict(orient="records")}
