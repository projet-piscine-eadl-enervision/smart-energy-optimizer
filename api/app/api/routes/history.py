"""Historique des données de consommation (série temporelle TimescaleDB).

TimescaleDB brille ici : requêtes time_bucket() pour agréger par heure/jour.
Exemple de vraie requête à mettre plus tard :
    SELECT time_bucket('1 hour', ts) AS bucket, avg(consumption_kw)
    FROM measurements WHERE ts > now() - interval '7 days' GROUP BY bucket;
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.energy import ConsumptionPoint

router = APIRouter(prefix="/history", tags=["History"])


@router.get("", response_model=list[ConsumptionPoint], summary="Consumption history")
async def get_history(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(default=7, ge=1, le=90),
):
    now = datetime.now(UTC)
    # TODO: remplacer par une requête time_bucket sur TimescaleDB
    return [
        ConsumptionPoint(
            timestamp=now - timedelta(hours=h),
            consumption_kw=2.5 + (h % 12) * 0.3,
        )
        for h in range(days * 24)
    ]
