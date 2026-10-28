"""Prévisions de consommation et heures de pic, lues dans ml.prediction.

Le module ML écrit ses prévisions heure par heure (ml.prediction) ; cette route ne fait que les lire.
Pour chaque heure et chaque site, la dernière écriture fait foi (une relance du ML met à jour
la prévision). Sans prévision à venir, la liste est vide. Le drapeau de pic est celui du site ;
il n'a pas de sens pour un total, où il reste vide.
"""
from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser, DbSession, site_scope
from app.schemas.energy import PeakHour, Prediction

router = APIRouter(prefix="/predictions", tags=["Predictions"])

TOTAL_SITES = "ALL"

# Dernière prévision écrite pour chaque (site, heure), de l'heure en cours à :hours heures plus tard
LATEST = """
SELECT DISTINCT ON (site_id, target_time)
       target_time, site_id, predicted_kw, is_peak, model_version
FROM ml.prediction
WHERE target_time >= date_trunc('hour', now())
  AND target_time <  date_trunc('hour', now()) + make_interval(hours => :hours)
  {site_filter}
ORDER BY site_id, target_time, predicted_at DESC
"""

BY_SITE_SQL = text(
    f"""
SELECT target_time, site_id, predicted_kw, is_peak, model_version
FROM ({LATEST.format(site_filter="AND site_id = :site_id")}) latest
ORDER BY target_time
"""
)

# Sans site : un point par heure, somme des sites. Le seuil de pic est propre à chaque site : pas de pic pour le total
TOTAL_SQL = text(
    f"""
WITH latest AS ({LATEST.format(site_filter="")})
SELECT target_time, '{TOTAL_SITES}' AS site_id, sum(predicted_kw) AS predicted_kw,
       NULL::boolean AS is_peak,
       string_agg(DISTINCT model_version, ',' ORDER BY model_version) AS model_version
FROM latest
GROUP BY target_time
ORDER BY target_time
"""
)


# Heures annoncées en pic : le drapeau est lu sur la dernière écriture de chaque (site, heure), pas sur
# une version plus ancienne. Le seuil est celui du site pour la version qui a prévu cette heure
PEAKS_SQL = text(
    f"""
WITH latest AS ({LATEST.format(site_filter="AND (CAST(:site_id AS text) IS NULL OR site_id = :site_id)")})
SELECT l.target_time, l.site_id, l.predicted_kw, t.threshold_kw, l.model_version
FROM latest l
LEFT JOIN ml.peak_threshold t ON t.model_version = l.model_version AND t.site_id = l.site_id
WHERE l.is_peak
ORDER BY l.target_time, l.site_id
"""
)


async def fetch_predictions(db: DbSession, hours: int, site_id: str | None) -> list[Prediction]:
    if site_id:
        result = await db.execute(BY_SITE_SQL, {"hours": hours, "site_id": site_id})
    else:
        result = await db.execute(TOTAL_SQL, {"hours": hours})
    return [
        Prediction(
            timestamp=row.target_time,
            site_id=row.site_id,
            predicted_kw=float(row.predicted_kw),
            is_peak=row.is_peak,
            model_version=row.model_version,
        )
        for row in result
    ]


@router.get("", response_model=list[Prediction], summary="Consumption forecast")
async def get_peak_predictions(
    current_user: CurrentUser,
    db: DbSession,
    hours: int = Query(default=24, ge=1, le=72, description="Horizon, en heures"),
    site_id: str | None = Query(default=None, description="Un site ; sans valeur, le total des sites"),
):
    return await fetch_predictions(db, hours, site_scope(current_user, site_id))


@router.get("/peaks", response_model=list[PeakHour], summary="Predicted consumption peaks")
async def get_predicted_peaks(
    current_user: CurrentUser,
    db: DbSession,
    hours: int = Query(default=24, ge=1, le=72, description="Horizon, en heures"),
    site_id: str | None = Query(default=None, description="Un site ; sans valeur, tous les sites"),
):
    """Heures prévues au-dessus du seuil de pic de leur site, avec ce seuil et le dépassement."""
    result = await db.execute(PEAKS_SQL, {"hours": hours, "site_id": site_scope(current_user, site_id)})
    peaks = []
    for row in result:
        predicted = float(row.predicted_kw)
        threshold = None if row.threshold_kw is None else float(row.threshold_kw)
        peaks.append(
            PeakHour(
                timestamp=row.target_time,
                site_id=row.site_id,
                predicted_kw=predicted,
                threshold_kw=threshold,
                excess_kw=None if threshold is None else predicted - threshold,
                model_version=row.model_version,
            )
        )
    return peaks
