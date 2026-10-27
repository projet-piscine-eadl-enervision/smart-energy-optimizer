"""Alertes des sites, lues dans core.alert.

Le mock ne renvoie que les alertes actives, et ses identifiants ne sont pas stables d'un appel à
l'autre (le suffixe est l'heure de la requête) : une alerte ne « disparaît » donc jamais de la
réponse, elle est remplacée. L'état se déduit de la fraîcheur : une alerte est active tant qu'elle a
été vue dans les ACTIVE_MINUTES dernières minutes et qu'aucune résolution n'est enregistrée.

`since` sert à l'interrogation incrémentale du tableau de bord : seules les alertes reçues après cet
instant sont renvoyées.
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.api.deps import CurrentUser, DbSession
from app.schemas.alerts import Alert

router = APIRouter(prefix="/alerts", tags=["Alerts"])

ACTIVE_MINUTES = 15

ALERTS_SQL = text(
    """
WITH alerts AS (
    SELECT a.alert_id, a.time AS ts, coalesce(a.last_seen_at, a.time) AS received_at,
           a.site_id, s.site_name, a.severity, a.alert_type, t.label AS alert_label,
           a.message, a.value, a.threshold, a.origin,
           CASE WHEN a.resolved_at IS NULL
                     AND coalesce(a.last_seen_at, a.time) >= now() - make_interval(mins => :active_minutes)
                THEN 'active' ELSE 'resolved' END AS status
    FROM core.alert a
    JOIN ref.site s ON s.site_id = a.site_id
    JOIN ref.alert_type t ON t.alert_type = a.alert_type
    WHERE (CAST(:site_id AS text) IS NULL OR a.site_id = :site_id)
      AND (CAST(:since AS timestamptz) IS NULL OR coalesce(a.last_seen_at, a.time) > :since)
)
SELECT * FROM alerts
WHERE :status = 'all' OR status = :status
ORDER BY received_at DESC, alert_id
LIMIT :limit
"""
)


async def fetch_alerts(
    db: DbSession, site_id: str | None, status: str, since: datetime | None, limit: int
) -> list[Alert]:
    params = {
        "site_id": site_id,
        "since": since,
        "status": status,
        "limit": limit,
        "active_minutes": ACTIVE_MINUTES,
    }
    result = await db.execute(ALERTS_SQL, params)
    return [
        Alert(
            alert_id=row.alert_id,
            timestamp=row.ts,
            received_at=row.received_at,
            site_id=row.site_id,
            site_name=row.site_name,
            severity=row.severity,
            alert_type=row.alert_type,
            alert_label=row.alert_label,
            message=row.message,
            value=None if row.value is None else float(row.value),
            threshold=None if row.threshold is None else float(row.threshold),
            origin=row.origin,
            status=row.status,
        )
        for row in result
    ]


@router.get("", response_model=list[Alert], summary="Site alerts")
async def get_alerts(
    current_user: CurrentUser,
    db: DbSession,
    site_id: str | None = Query(default=None, description="Un site ; sans valeur, tous les sites"),
    status: Literal["active", "resolved", "all"] = Query(default="active"),
    since: datetime | None = Query(default=None, description="Alertes reçues après cet instant (UTC)"),
    limit: int = Query(default=50, ge=1, le=200),
):
    return await fetch_alerts(db, site_id, status, since, limit)
