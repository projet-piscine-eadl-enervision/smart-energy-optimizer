"""Prédiction : le champion prévoit les 24 prochaines heures, écrites dans ml.prediction.

Lancement manuel : docker compose run --rm ml python -m enervision_ml.predict
(le lancement toutes les heures viendra avec le service ML)
"""

from datetime import timedelta

import mlflow
import pandas as pd
from mlflow import MlflowClient

from enervision_ml import registry
from enervision_ml.config import HORIZON_HOURS, MODEL_NAME, load_settings
from enervision_ml.data import latest_hour, load_hourly, save_predictions
from enervision_ml.features import (
    FEATURE_COLUMNS,
    add_features,
    extend_future,
    mask_unreliable_hours,
    to_hourly_grid,
)

# Historique chargé : lag_168 de la dernière heure prévue, plus une marge. Inutile au profil
# (calendrier seul), mais le service ne doit pas dépendre du modèle qui est champion
HISTORY_HOURS = 168 + HORIZON_HOURS + 24


def run() -> int:
    """Prévoit et enregistre ; renvoie le nombre de prédictions écrites."""
    settings = load_settings()
    mlflow.set_tracking_uri(settings.tracking_uri)

    champion = registry.get_alias(MlflowClient(), registry.CHAMPION)
    if champion is None:
        raise SystemExit("Aucun modèle champion : lancer d'abord l'entraînement.")
    last = latest_hour(settings.database_url)
    if last is None:
        raise SystemExit("analytics.energy_hourly est vide : rien à prévoir.")

    history = load_hourly(settings.database_url, start=last - timedelta(hours=HISTORY_HOURS))
    # L'heure en cours est incomplète (agrégat temps réel) : on prévoit à partir de la précédente
    history = history[history["hour"] < pd.Timestamp.now(tz="UTC").floor("h")]

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
        print(f"{skipped} heure(s) sans prévision : historique insuffisant")

    # ml.prediction.model_version est du texte ; MLflow donne un entier
    version = str(champion.version)
    count = save_predictions(settings.database_url, predictions, version)
    print(f"{count} prédictions écrites ({MODEL_NAME} v{version})")
    return count


if __name__ == "__main__":
    run()
