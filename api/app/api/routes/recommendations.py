"""Recommandations d'optimisation de la consommation."""
from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.energy import Recommendation

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=list[Recommendation], summary="List all recommandations")
async def get_recommendations(current_user: CurrentUser, db: DbSession):
    # TODO: générer à partir des prédictions + règles métier / IA
    return [
        Recommendation(
            id=1,
            title="Décaler le chauffage de la piscine",
            message=(
                "Un pic est prévu à 19h. Lancez la filtration avant 17h. "
                "Pour éviter la tranche horaire chère."
            ),
            estimated_saving_kw=1.8,
        ),
        Recommendation(
            id=2,
            title="Mode éco la nuit",
            message=(
                "Consommation nocturne stable : activez le mode éco. "
                "Entre 23h et 6h."
            ),
            estimated_saving_kw=0.9,
        ),
    ]
