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

# Surveillance du modèle en service (monitor.py). Les entrées du modèle sont calendaires (site, mois,
# type de jour, heure) : elles ne peuvent pas dériver. On surveille la consommation elle-même (dérive des
# données), l'erreur face à la mesure (dérive du concept), la qualité des mesures et la fraîcheur.
DRIFT_WINDOW_DAYS = 7  # fenêtre récente
DRIFT_MIN_HOURS = 72  # en dessous, trop peu d'heures fiables pour conclure : « insufficient »
# Écart moyen relatif à la consommation habituelle du site (analytics.site_baseline). Le bruit du mock
# est de 3 % à 10 % par mesure et s'annule sur une semaine : 10 % d'écart moyen est un vrai changement de niveau
DRIFT_BIAS_MAX = 0.10
# Part des heures à plus de DRIFT_OUTLIER_Z écarts types de l'habitude du site : 0,3 % attendus
# si les données sont stables, on alerte à 5 %
DRIFT_OUTLIER_Z = 3
DRIFT_OUTLIER_SHARE_MAX = 0.05
# Part des mesures sans consommation sur la fenêtre : 2 % à 3 % dans le jeu fourni (pannes de capteur)
MISSING_SHARE_MAX = 0.20
# Erreur récente (nMAE par jour, face à la mesure) rapportée à l'erreur de validation du champion
CONCEPT_NMAE_RATIO_MAX = 1.5
CONCEPT_MIN_DAYS = 3
# Âge de la dernière prévision : elle tourne toutes les heures, plus de deux heures signale une panne
PREDICTION_AGE_MAX_HOURS = 2.0


@dataclass(frozen=True)
class Settings:
    database_url: str
    tracking_uri: str
    public_url: str | None
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
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        tracking_uri=tracking_uri,
        # Adresse d'MLflow telle qu'on l'ouvre depuis son poste (celle du réseau Docker ne s'ouvre pas) ;
        # à défaut, celle de suivi. Aucune en production : MLflow n'y est pas déployé
        public_url=None
        if os.getenv("APP_ENV", "dev") == "production"
        else os.getenv("MLFLOW_PUBLIC_URL") or tracking_uri,
        code_version=os.getenv("GIT_SHA", "dev"),
        data_end=parse_data_end(os.getenv("ML_DATA_END")),
    )
