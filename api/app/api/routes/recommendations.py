"""Recommandations, lues dans app.recommendation.

Elles sont créées par app.refresh_recommendations() après chaque prévision du ML : un conseil par site,
heure et règle (pic prévu, ou type d'alerte). Fenêtre : alertes des dernières 24 h et pics prévus dans
les :hours prochaines heures. L'économie estimée d'un pic prévu est la part décalable de la consommation
(ml.model_run.shiftable_ratio), limitée au dépassement du seuil du site ; elle est vide pour les autres.
"""
from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser, DbSession
from app.schemas.energy import Recommendation

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])

RECOMMENDATIONS_SQL = text(
    """
WITH latest AS (
    SELECT DISTINCT ON (site_id, target_time) site_id, target_time, predicted_kw, is_peak, model_version
    FROM ml.prediction
    WHERE target_time >= date_trunc('hour', now()) - interval '24 hours'
      AND target_time <  date_trunc('hour', now()) + make_interval(hours => :hours)
    ORDER BY site_id, target_time, predicted_at DESC
)
SELECT r.recommendation_id, r.site_id, s.site_name, r.target_time,
       t.trigger_rule AS alert_type, a.label AS alert_label, t.message,
       CASE WHEN t.trigger_rule = 'threshold' AND l.is_peak
            THEN least(greatest(l.predicted_kw - th.threshold_kw, 0), mr.shiftable_ratio * l.predicted_kw)
       END AS saving_kw
FROM app.recommendation r
JOIN ref.recommendation_type t USING (recommendation_type_id)
JOIN ref.alert_type a ON a.alert_type = t.trigger_rule
JOIN ref.site s ON s.site_id = r.site_id
LEFT JOIN latest l ON l.site_id = r.site_id AND l.target_time = r.target_time
LEFT JOIN ml.peak_threshold th ON th.model_version = l.model_version AND th.site_id = l.site_id
LEFT JOIN ml.model_run mr ON mr.model_version = l.model_version
WHERE r.target_time >= date_trunc('hour', now()) - interval '24 hours'
  AND r.target_time <  date_trunc('hour', now()) + make_interval(hours => :hours)
  AND (CAST(:site_id AS text) IS NULL OR r.site_id = :site_id)
ORDER BY r.target_time, r.site_id, r.recommendation_id
LIMIT :limit
"""
)


async def fetch_recommendations(
    db: DbSession, hours: int, site_id: str | None, limit: int
) -> list[Recommendation]:
    result = await db.execute(RECOMMENDATIONS_SQL, {"hours": hours, "site_id": site_id, "limit": limit})
    return [
        Recommendation(
            id=row.recommendation_id,
            title=f"{row.alert_label} : {row.site_name}",
            message=row.message,
            estimated_saving_kw=None if row.saving_kw is None else float(row.saving_kw),
            site_id=row.site_id,
            target_time=row.target_time,
            alert_type=row.alert_type,
        )
        for row in result
    ]


@router.get("", response_model=list[Recommendation], summary="Optimisation recommendations")
async def get_recommendations(
    current_user: CurrentUser,
    db: DbSession,
    hours: int = Query(default=24, ge=1, le=72, description="Horizon des pics prévus, en heures"),
    site_id: str | None = Query(default=None, description="Un site ; sans valeur, tous les sites"),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await fetch_recommendations(db, hours, site_id, limit)
