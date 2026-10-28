"""Sites : liste, consommation par période et qualité des relevés.

La consommation vient de analytics.energy_hourly (heure) et analytics.energy_daily (jour, découpe en
Europe/Paris) ; la semaine et le mois regroupent les jours. Comme pour /history, les heures dont plus de
la moitié des mesures manquent sont écartées. L'énergie d'une heure est la puissance moyenne (kW) × 1 h.
La qualité ne dépend pas du nombre de relevés : le rattrapage écrit une mesure par heure, le collecteur
une par minute.
"""
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.api.deps import CurrentUser, DbSession
from app.schemas.sites import Period, Site, SiteConsumptionPoint, SiteQuality

router = APIRouter(prefix="/sites", tags=["Sites"])

# Fenêtre par défaut selon la période, en jours
DEFAULT_DAYS = {"hour": 2, "day": 30, "week": 90, "month": 365}

SITES_SQL = text(
    """
SELECT s.site_id, s.site_name, s.site_type, s.location, s.capacity_kw, s.status,
       l.consumption_kw AS last_consumption_kw,
       extract(epoch FROM l.age) / 60 AS last_reading_age_minutes,
       l.last_quality
FROM ref.site s
LEFT JOIN analytics.latest_reading l ON l.site_id = s.site_id
ORDER BY s.site_id
"""
)

SITE_EXISTS_SQL = text("SELECT 1 FROM ref.site WHERE site_id = :site_id")

HOURLY_SQL = text(
    """
SELECT hour AS ts, energy_kwh, max_consumption_kw AS max_kw
FROM analytics.energy_hourly
WHERE site_id = :site_id
  AND hour >= date_trunc('hour', now()) - make_interval(days => :days)
  AND hour <  date_trunc('hour', now())
  AND avg_consumption_kw IS NOT NULL
  AND (nb_missing <= 0.5 * nb_readings OR nb_readings - nb_missing >= 10)
ORDER BY hour
"""
)

# Le jour en cours est exclu : il est incomplet
DAILY_SQL = text(
    """
SELECT date_trunc(:unit, day, 'Europe/Paris') AS ts, sum(energy_kwh) AS energy_kwh, max(max_consumption_kw) AS max_kw
FROM analytics.energy_daily
WHERE site_id = :site_id
  AND day >= date_trunc('day', now() - make_interval(days => :days))
  AND day <  time_bucket(INTERVAL '1 day', now(), 'Europe/Paris')
  AND energy_kwh IS NOT NULL
GROUP BY 1
ORDER BY 1
"""
)

QUALITY_SQL = text(
    """
SELECT count(*) AS readings,
       count(*) FILTER (WHERE consumption_kw IS NULL) AS missing,
       count(*) FILTER (WHERE data_quality = 'good') AS good,
       count(*) FILTER (WHERE data_quality = 'partial') AS partial,
       count(*) FILTER (WHERE data_quality = 'degraded') AS degraded,
       count(*) FILTER (WHERE data_quality = 'critical') AS critical,
       (SELECT count(*) FROM core.sensor_status
         WHERE site_id = :site_id AND started_at >= now() - make_interval(days => :days)) AS outages
FROM core.energy_reading
WHERE site_id = :site_id
  AND time >= now() - make_interval(days => :days)
"""
)


def _number(value) -> float | None:
    return None if value is None else float(value)


async def require_site(db: DbSession, site_id: str) -> None:
    if (await db.execute(SITE_EXISTS_SQL, {"site_id": site_id})).first() is None:
        raise HTTPException(status_code=404, detail="Site inconnu")


@router.get("", response_model=list[Site], summary="Sites")
async def get_sites(current_user: CurrentUser, db: DbSession):
    result = await db.execute(SITES_SQL)
    return [
        Site(
            site_id=row.site_id,
            site_name=row.site_name,
            site_type=row.site_type,
            location=row.location,
            capacity_kw=float(row.capacity_kw),
            status=row.status,
            last_consumption_kw=_number(row.last_consumption_kw),
            last_reading_age_minutes=_number(row.last_reading_age_minutes),
            last_quality=row.last_quality,
        )
        for row in result
    ]


@router.get(
    "/{site_id}/consumption",
    response_model=list[SiteConsumptionPoint],
    summary="Site consumption by period",
)
async def get_site_consumption(
    site_id: str,
    current_user: CurrentUser,
    db: DbSession,
    period: Annotated[Period, Query()] = "day",
    days: int | None = Query(default=None, ge=1, le=730, description="Fenêtre ; selon la période par défaut"),
):
    await require_site(db, site_id)
    days = days or DEFAULT_DAYS[period]
    if period == "hour":
        result = await db.execute(HOURLY_SQL, {"site_id": site_id, "days": days})
    else:
        unit = "day" if period == "day" else period
        result = await db.execute(DAILY_SQL, {"site_id": site_id, "days": days, "unit": unit})
    return [
        SiteConsumptionPoint(timestamp=row.ts, energy_kwh=float(row.energy_kwh), max_kw=_number(row.max_kw))
        for row in result
    ]


@router.get("/{site_id}/quality", response_model=SiteQuality, summary="Site data quality")
async def get_site_quality(
    site_id: str,
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(default=7, ge=1, le=30),
):
    await require_site(db, site_id)
    row = (await db.execute(QUALITY_SQL, {"site_id": site_id, "days": days})).first()
    return SiteQuality(
        site_id=site_id,
        days=days,
        readings=row.readings,
        missing_ratio=round(row.missing / row.readings, 4) if row.readings else None,
        by_quality={
            "good": row.good,
            "partial": row.partial,
            "degraded": row.degraded,
            "critical": row.critical,
        },
        sensor_outages=row.outages,
    )
