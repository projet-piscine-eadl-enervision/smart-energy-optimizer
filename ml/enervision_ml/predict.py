"""Prédiction : le champion prévoit les 24 prochaines heures, écrites dans ml.prediction.

Lancement manuel : docker compose run --rm ml python -m enervision_ml.predict
(le lancement toutes les heures viendra avec le service ML)
"""

import logging
from datetime import timedelta

import mlflow
import pandas as pd
import psycopg
from mlflow import MlflowClient

from enervision_ml import registry
from enervision_ml.config import (
    HORIZON_HOURS,
    MAX_DATA_AGE_HOURS,
    MODEL_NAME,
    load_settings,
)
from enervision_ml.data import (
    latest_hour,
    load_hourly,
    refresh_recommendations,
    save_predictions,
)
from enervision_ml.features import (
    FEATURE_COLUMNS,
    add_features,
    extend_future,
    mask_unreliable_hours,
    to_hourly_grid,
)
from enervision_ml.logs import configure

log = logging.getLogger(__name__)

# Historique chargé : lag_168 de la dernière heure prévue, plus une marge. Inutile au profil
# (calendrier seul), mais le service ne doit pas dépendre du modèle qui est champion
HISTORY_HOURS = 168 + HORIZON_HOURS + 24


def check_fresh(last: pd.Timestamp, now: pd.Timestamp) -> None:
    """Refuse de prévoir si la dernière mesure est trop ancienne.

    Les prévisions partent de la dernière heure connue : avec un collecteur arrêté, elles
    porteraient sur des heures passées et seraient écrites comme si elles étaient à venir.
    """
    age = now - pd.Timestamp(last).tz_convert("UTC")
    if age > pd.Timedelta(hours=MAX_DATA_AGE_HOURS):
        raise SystemExit(
            f"Données trop anciennes : dernière heure {last:%Y-%m-%d %H:%M} UTC, "
            f"{age // pd.Timedelta(hours=1)} h de retard (maximum {MAX_DATA_AGE_HOURS} h). "
            "Le collecteur est-il arrêté ? Aucune prévision écrite."
        )


def run(now: pd.Timestamp | None = None) -> int:
    """Prévoit et enregistre ; renvoie le nombre de prédictions écrites."""
    configure()
    now = (now if now is not None else pd.Timestamp.now(tz="UTC")).floor("h")
    settings = load_settings()
    mlflow.set_tracking_uri(settings.tracking_uri)

    champion = registry.get_alias(MlflowClient(), registry.CHAMPION)
    if champion is None:
        raise SystemExit("Aucun modèle champion : lancer d'abord l'entraînement.")
    last = latest_hour(settings.database_url)
    if last is None:
        raise SystemExit("analytics.energy_hourly est vide : rien à prévoir.")
    check_fresh(last, now)

    history = load_hourly(settings.database_url, start=last - timedelta(hours=HISTORY_HOURS))
    # L'heure en cours est incomplète (agrégat temps réel) : on prévoit à partir de la précédente
    history = history[history["hour"] < now]

    frame = add_features(extend_future(to_hourly_grid(mask_unreliable_hours(history))))
    future = frame[frame["is_future"]]
    model = registry.load_model(champion.version)
    output = model.predict(future[["site_id", *FEATURE_COLUMNS]])

    predictions = pd.DataFrame(
        {
            "target_time": future["hour"],
            "site_id": future["site_id"],
            "predicted_kw": output["predicted_kw"],
            "is_peak": output["is_peak"],
        }
    ).dropna(subset=["predicted_kw"])
    skipped = len(future) - len(predictions)
    if skipped:
        log.warning("%d heure(s) sans prévision : historique insuffisant", skipped)
        print(f"{skipped} heure(s) sans prévision : historique insuffisant")

    # ml.prediction.model_version est du texte ; MLflow donne un entier
    version = str(champion.version)
    count = save_predictions(settings.database_url, predictions, version)
    log.info("prévisions écrites version=%s nombre=%d", version, count)
    print(f"{count} prédictions écrites ({MODEL_NAME} v{version})")
    try:
        created = refresh_recommendations(settings.database_url)
    except psycopg.Error as exc:
        # Les prévisions sont déjà enregistrées ; l'échec reste visible (code de sortie non nul)
        raise SystemExit(f"Prédictions écrites, mais recommandations non recalculées : {exc}") from exc
    print(f"{created} recommandation(s) créée(s)")
    return count


if __name__ == "__main__":
    run()
