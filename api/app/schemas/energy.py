"""Schémas Pydantic pour les données énergétiques exposées au front (documentés dans /docs)."""
from datetime import datetime

from pydantic import BaseModel, Field


class Prediction(BaseModel):
    """Consommation prévue pour une heure, lue dans ml.prediction (dernière écriture du module ML)."""

    timestamp: datetime = Field(description="Début de l'heure prévue (UTC)", examples=["2026-10-27T14:00:00Z"])
    site_id: str = Field(description="Site prévu ; ALL pour le total des sites", examples=["SITE001"])
    predicted_kw: float = Field(description="Puissance moyenne prévue sur l'heure, en kW", examples=[132.5])
    is_peak: bool | None = Field(
        description="L'heure dépasse le seuil de pic du site (1,25 fois sa consommation moyenne). "
        "Vide pour le total des sites : ce seuil est propre à chaque site",
        examples=[True],
    )
    model_version: str = Field(description="Version du modèle (registre MLflow) qui a prévu cette heure", examples=["3"])
    confidence: float | None = Field(
        default=None, description="Toujours vide : le modèle ne produit aucune mesure d'incertitude"
    )


class PeakHour(BaseModel):
    """Heure prévue au-dessus du seuil de pic d'un site."""

    timestamp: datetime = Field(description="Début de l'heure (UTC)", examples=["2026-10-27T14:00:00Z"])
    site_id: str = Field(description="Site concerné", examples=["SITE001"])
    predicted_kw: float = Field(description="Puissance moyenne prévue, en kW", examples=[132.5])
    threshold_kw: float | None = Field(
        description="Seuil de pic du site pour cette version du modèle, en kW (vide s'il est inconnu)", examples=[120.0]
    )
    excess_kw: float | None = Field(description="Dépassement prévu du seuil, en kW", examples=[12.5])
    model_version: str = Field(description="Version du modèle qui a prévu cette heure", examples=["3"])


class ConsumptionPoint(BaseModel):
    """Consommation mesurée sur une heure complète, lue dans analytics.energy_hourly."""

    timestamp: datetime = Field(description="Début de l'heure (UTC)", examples=["2026-10-27T13:00:00Z"])
    consumption_kw: float = Field(description="Puissance moyenne sur l'heure, en kW ; somme des sites sans site_id", examples=[640.2])


class Recommendation(BaseModel):
    """Conseil pour un site et une heure, déduit d'un pic prévu ou d'une alerte (app.recommendation)."""

    id: int = Field(description="Identifiant du conseil", examples=[42])
    title: str = Field(description="Type d'alerte et site", examples=["Dépassement du seuil : Bureau Paris"])
    message: str = Field(description="Conseil rédigé à l'avance pour ce type de site et d'alerte")
    estimated_saving_kw: float | None = Field(
        description="Part décalable du dépassement prévu, en kW (pic prévu seulement, vide pour une alerte)",
        examples=[10.0],
    )
    site_id: str = Field(description="Site concerné", examples=["SITE001"])
    target_time: datetime = Field(description="Heure du pic prévu ou de l'alerte (UTC)")
    alert_type: str = Field(description="Règle déclenchante : threshold (pic prévu), spike, plateau, drop, outage, anomaly, sensor", examples=["threshold"])
