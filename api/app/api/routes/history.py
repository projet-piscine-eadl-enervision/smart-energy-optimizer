"""Historique de consommation, lu dans analytics.energy_hourly (agrégat horaire TimescaleDB).

Un point par heure. L'heure en cours est exclue (l'agrégat la calcule en direct, elle est incomplète),
ainsi que les heures sans assez de mesures valides : au plus la moitié manque, ou au moins 10 sont
valides (le collecteur en direct perd beaucoup de relevés, mais une dizaine suffit pour une moyenne).
Sans site, c'est la somme des sites : une heure où un site manque est écartée plutôt que de creuser la
courbe.
"""
from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser, DbSession, site_scope
from app.schemas.energy import ConsumptionPoint

router = APIRouter(prefix="/history", tags=["History"])

# Heures complètes des :days derniers jours, fiables (au plus la moitié manque, ou 10 mesures valides)
RELIABLE = """
FROM analytics.energy_hourly
WHERE hour >= date_trunc('hour', now()) - make_interval(days => :days)
  AND hour <  date_trunc('hour', now())
  AND avg_consumption_kw IS NOT NULL
  AND (nb_missing <= 0.5 * nb_readings OR nb_readings - nb_missing >= 10)
"""

BY_SITE_SQL = text(
    f"""
SELECT hour AS ts, avg_consumption_kw AS consumption_kw
{RELIABLE}
  AND site_id = :site_id
ORDER BY hour
"""
)

TOTAL_SQL = text(
    f"""
SELECT hour AS ts, sum(avg_consumption_kw) AS consumption_kw
{RELIABLE}
GROUP BY hour
HAVING count(*) = (SELECT count(*) FROM ref.site)
ORDER BY hour
"""
)


async def fetch_history(db: DbSession, days: int, site_id: str | None) -> list[ConsumptionPoint]:
    if site_id:
        result = await db.execute(BY_SITE_SQL, {"days": days, "site_id": site_id})
    else:
        result = await db.execute(TOTAL_SQL, {"days": days})
    return [ConsumptionPoint(timestamp=row.ts, consumption_kw=float(row.consumption_kw)) for row in result]


@router.get("", response_model=list[ConsumptionPoint], summary="Consumption history")
async def get_history(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(default=7, ge=1, le=90),
    site_id: str | None = Query(default=None, description="Un site ; sans valeur, le total des sites"),
):
    return await fetch_history(db, days, site_scope(current_user, site_id))
