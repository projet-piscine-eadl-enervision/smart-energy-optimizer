"""Paramètres du module ML : constantes du modèle et variables d'environnement.

Les choix s'appuient sur l'analyse de l'API Mock (docs/analyse-api-mock.md), citée par
numéro de constat.
"""

import os
from dataclasses import dataclass
from datetime import UTC, datetime, time

from dotenv import load_dotenv

EXPERIMENT = "enervision"
# Nom du modèle dans le registre MLflow ; ses alias champion et challenger désignent des versions
MODEL_NAME = "enervision-consumption"

# Prévision des 24 prochaines heures, heure par heure
HORIZON_HOURS = 24
# Le profil du mock suit l'heure UTC, sans changement d'heure (constat 11)
CALENDAR_TZ = "UTC"

# Pic de demande : prévision au-dessus de PEAK_RATIO fois la consommation moyenne du site.
# Un quantile marquerait du bruit comme pic sur les sites plats, datacenter et hôpital (constat 9)
PEAK_RATIO = 1.25

# Processus métier simulé (KPI d'impact) : la veille, le gestionnaire du site reçoit les pics
# prévus et décale une part de la consommation de ces heures vers les heures creuses. Chaque kWh
# au-dessus du seuil de pic est facturé en dépassement. Ce sont des hypothèses, pas des mesures :
# le mock ne donne aucun coût (constat 14)
SHIFTABLE_RATIO = 0.10  # part de la consommation d'une heure qu'on sait décaler
PEAK_PENALTY_EUR_KWH = 0.15  # coût d'un kWh consommé au-dessus du seuil de pic

# Une heure dont plus de la moitié des mesures n'ont pas de consommation n'est pas fiable :
# sa moyenne repose sur trop peu de points (constat 10)
MAX_MISSING_RATIO = 0.5

# Découpage temporel : les derniers jours servent au test, ceux d'avant à la validation
VALIDATION_DAYS = 60
TEST_DAYS = 60
# Le facteur du mois n'est appris qu'avec au moins un an d'entraînement (constat 5)
MIN_TRAIN_DAYS = 365

# Au-delà, les mesures sont trop anciennes pour prévoir : le collecteur est sans doute arrêté
MAX_DATA_AGE_HOURS = 3


@dataclass(frozen=True)
class Settings:
    database_url: str
    tracking_uri: str
    code_version: str
    data_end: datetime


def parse_data_end(value: str | None, now: datetime | None = None) -> datetime:
    """ML_DATA_END (ISO, UTC par défaut) : première heure exclue de l'entraînement.

    Sans valeur, minuit UTC du jour : les fenêtres de validation et de test ne glissent qu'une
    fois par jour, au lieu d'une fois par heure collectée, et deux entraînements du même jour
    portent sur les mêmes données.
    """
    if not value:
        return datetime.combine((now or datetime.now(UTC)).date(), time.min, tzinfo=UTC)
    end = datetime.fromisoformat(value)
    return end if end.tzinfo else end.replace(tzinfo=UTC)


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
        code_version=os.getenv("GIT_SHA", "dev"),
        data_end=parse_data_end(os.getenv("ML_DATA_END")),
    )
