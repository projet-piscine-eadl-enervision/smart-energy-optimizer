"""Paramètres du module ML : constantes du modèle et variables d'environnement.

Les choix s'appuient sur l'analyse de l'API Mock (docs/analyse-api-mock.md), citée par
numéro de constat.
"""

import os
from dataclasses import dataclass

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

# Une heure dont plus de la moitié des mesures n'ont pas de consommation n'est pas fiable :
# sa moyenne repose sur trop peu de points (constat 10)
MAX_MISSING_RATIO = 0.5

# Découpage temporel : les derniers jours servent au test, ceux d'avant à la validation
VALIDATION_DAYS = 60
TEST_DAYS = 60
# Le facteur du mois n'est appris qu'avec au moins un an d'entraînement (constat 5)
MIN_TRAIN_DAYS = 365


@dataclass(frozen=True)
class Settings:
    database_url: str
    tracking_uri: str
    code_version: str


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000"),
        code_version=os.getenv("GIT_SHA", "dev"),
    )
