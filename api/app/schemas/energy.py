"""Schémas Pydantic pour les données énergétiques exposées au front."""
from datetime import datetime

from pydantic import BaseModel


class Prediction(BaseModel):
    """Consommation prévue pour une heure.

    is_peak : l'heure dépasse le seuil de pic du site (1,25 fois sa consommation moyenne). Ce seuil
    est propre à chaque site : il est vide pour le total des sites (site_id vaut ALL).
    confidence reste vide : le modèle ne produit aucune mesure d'incertitude.
    """

    timestamp: datetime
    site_id: str
    predicted_kw: float
    is_peak: bool | None
    model_version: str
    confidence: float | None = None


class ConsumptionPoint(BaseModel):
    timestamp: datetime
    consumption_kw: float


class Recommendation(BaseModel):
    """Conseil pour un site et une heure.

    estimated_saving_kw : part décalable du dépassement prévu (pic prévu seulement, vide sinon).
    """

    id: int
    title: str
    message: str
    estimated_saving_kw: float | None
    site_id: str
    target_time: datetime
    alert_type: str


class PeakHour(BaseModel):
    """Heure prévue au-dessus du seuil de pic d'un site."""

    timestamp: datetime
    site_id: str
    predicted_kw: float
    threshold_kw: float | None
    excess_kw: float | None
    model_version: str
