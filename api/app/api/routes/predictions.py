"""Prédictions de pics de consommation.

Pour l'instant renvoie des données d'exemple. Quand ton modèle IA et tes
tables TimescaleDB seront prêts, remplace le corps par une vraie requête
(db.execute(...)) — la structure de la route ne bougera pas.
"""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.energy import PeakPrediction

router = APIRouter(prefix="/predictions", tags=["Predictions"])


@router.get("", response_model=list[PeakPrediction], summary="Consumption predictions")
async def get_peak_predictions(current_user: CurrentUser, db: DbSession):
    now = datetime.now(UTC)
    # TODO: remplacer par la sortie du modèle IA + lecture TimescaleDB
    return [
        PeakPrediction(
            timestamp=now + timedelta(hours=h),
            predicted_kw=3.2 + h * 0.4,
            confidence=0.87,
        )
        for h in range(1, 7)
    ]
