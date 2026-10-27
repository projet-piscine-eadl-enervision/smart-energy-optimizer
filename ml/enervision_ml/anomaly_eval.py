"""Évaluation de la détection d'anomalies contre l'historique étiqueté (ml.history_labeled).

Lancement : docker compose run --rm ml python -m enervision_ml.anomaly_eval
La table est chargée par l'ETL (traitement load-history) ; tant qu'elle est vide, la commande le dit.

Deux détecteurs sont évalués sur les mêmes étiquettes (pic, chute, coupure, plateau) :
- l'écart au profil : une heure est anormale si elle s'écarte de plus de ANOMALY_Z écarts types et de plus de
  ANOMALY_MIN_DEVIATION du niveau habituel du site (même mois, même type de jour, même heure), comme
  le préconise l'analyse du mock (constat 9) ;
- la règle de pic du service : consommation au-dessus de PEAK_RATIO fois la moyenne du site.
Le profil est calculé sur les heures sans anomalie étiquetée. Les résultats vont dans MLflow, expérience
enervision-monitoring, pour juger la règle de pic sur une vérité terrain : elle attrape les pics étiquetés,
mais elle marque aussi les heures ouvrées normales d'un site à horaires fixes (un pic de demande n'est pas
une anomalie).
"""
import logging

import mlflow
import numpy as np
import pandas as pd

from enervision_ml import data
from enervision_ml.config import (
    ANOMALY_MIN_DEVIATION,
    ANOMALY_Z,
    PEAK_RATIO,
    load_settings,
)
from enervision_ml.logs import configure
from enervision_ml.monitor import EXPERIMENT

log = logging.getLogger(__name__)

PEAK_LIKE = ("spike", "plateau")  # étiquettes d'une consommation anormalement élevée


def add_calendar(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["month"] = frame["time"].dt.month
    frame["day_type"] = np.where(frame["time"].dt.dayofweek >= 5, "weekend", "weekday")
    frame["hod"] = frame["time"].dt.hour
    return frame


def evaluate(history: pd.DataFrame) -> dict[str, float]:
    """Rappel par type d'anomalie, précision et fausses alertes de chaque détecteur (fonction pure)."""
    frame = add_calendar(history)
    normal = frame[frame["anomaly_type"].isna()]
    keys = ["site_id", "month", "day_type", "hod"]
    profile = normal.groupby(keys)["consumption_kw"].agg(avg="mean", std="std").reset_index()
    site_mean = normal.groupby("site_id")["consumption_kw"].mean().rename("site_mean")
    frame = frame.merge(profile, on=keys, how="left").merge(site_mean, on="site_id", how="left")

    deviation = (frame["consumption_kw"] - frame["avg"]).abs()
    frame["profile_flag"] = (deviation > ANOMALY_Z * frame["std"]) & (deviation > ANOMALY_MIN_DEVIATION * frame["avg"])
    frame["peak_flag"] = frame["consumption_kw"] > PEAK_RATIO * frame["site_mean"]

    labeled = frame["anomaly_type"].notna()
    metrics: dict[str, float] = {"hours": float(len(frame)), "labeled_hours": float(labeled.sum())}
    for anomaly_type, hours in frame[labeled].groupby("anomaly_type"):
        metrics[f"profile_recall_{anomaly_type}"] = float(hours["profile_flag"].mean())
    peak_like = frame["anomaly_type"].isin(PEAK_LIKE)
    if peak_like.any():
        metrics["peak_rule_recall_spike_plateau"] = float(frame.loc[peak_like, "peak_flag"].mean())
    for name in ("profile_flag", "peak_flag"):
        flagged = frame[name]
        metrics[f"{name}_precision"] = float(labeled[flagged].mean()) if flagged.any() else 0.0
        metrics[f"{name}_false_alarm_rate"] = float(flagged[~labeled].mean()) if (~labeled).any() else 0.0
    return metrics


def run() -> dict[str, float]:
    configure()
    settings = load_settings()
    history = data.load_labeled_history(settings.database_url)
    if history.empty:
        raise SystemExit(
            "ml.history_labeled est vide : l'ETL doit d'abord charger l'historique étiqueté "
            "(traitement load-history)."
        )
    metrics = evaluate(history)
    try:
        mlflow.set_tracking_uri(settings.tracking_uri)
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name="anomaly_eval"):
            mlflow.log_params({"anomaly_z": ANOMALY_Z, "anomaly_min_deviation": ANOMALY_MIN_DEVIATION,
                               "peak_ratio": PEAK_RATIO})
            mlflow.log_metrics(metrics)
    except Exception as exc:  # noqa: BLE001 - MLflow est secondaire
        log.warning("évaluation non enregistrée dans MLflow : %s", type(exc).__name__)
    log.info("évaluation de la détection d'anomalies : %d heures, %d étiquetées",
             metrics["hours"], metrics["labeled_hours"])
    for name, value in sorted(metrics.items()):
        print(f"  {name} : {value:.3f}")
    return metrics


if __name__ == "__main__":
    run()
