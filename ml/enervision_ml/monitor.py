"""Surveillance du modèle en service : dérive des données, dérive du concept, qualité, fraîcheur.

Lancement manuel : docker compose run --rm ml python -m enervision_ml.monitor
(sur le staging, un minuteur le lance chaque jour : voir docs/deploiement-staging.md)

Chaque contrôle donne une valeur, un seuil et un statut : ok, alert, ou insufficient quand il n'y a pas
assez de données pour conclure. Les résultats vont dans ml.drift_metric (vues ml.model_health et
ml.model_status) et dans MLflow, expérience enervision-monitoring. Une alerte se lit aussi au code de
sortie (2), donc dans l'état du service systemd.
"""
import logging
from datetime import timedelta

import mlflow
import numpy as np
import pandas as pd

from enervision_ml import data
from enervision_ml.config import (
    CONCEPT_MIN_DAYS,
    CONCEPT_NMAE_RATIO_MAX,
    DRIFT_BIAS_MAX,
    DRIFT_MIN_HOURS,
    DRIFT_OUTLIER_SHARE_MAX,
    DRIFT_OUTLIER_Z,
    DRIFT_WINDOW_DAYS,
    MAX_MISSING_RATIO,
    MISSING_SHARE_MAX,
    PREDICTION_AGE_MAX_HOURS,
    load_settings,
)
from enervision_ml.logs import configure

log = logging.getLogger(__name__)

EXPERIMENT = "enervision-monitoring"
OK, ALERT, INSUFFICIENT = "ok", "alert", "insufficient"


def check(checked_at, version, site_id, metric, value, threshold, worse) -> dict:
    """Une ligne de ml.drift_metric ; worse(value) dit si la valeur dépasse le seuil."""
    if value is None or pd.isna(value):
        return {"checked_at": checked_at, "model_version": version, "site_id": site_id, "metric": metric,
                "value": None, "threshold": threshold, "status": INSUFFICIENT}
    return {"checked_at": checked_at, "model_version": version, "site_id": site_id, "metric": metric,
            "value": float(value), "threshold": threshold, "status": ALERT if worse(float(value)) else OK}


def assess(recent, baseline, daily_quality, val_nmae, ages, version, checked_at) -> list[dict]:
    """Calcule les contrôles de chaque site (fonction pure, testée sans base)."""
    rows = []
    reliable = recent[
        recent["consumption_kw"].notna() & (recent["nb_missing"] <= MAX_MISSING_RATIO * recent["nb_readings"])
    ].copy()
    reliable["month"] = reliable["hour"].dt.month
    reliable["day_type"] = np.where(reliable["hour"].dt.dayofweek >= 5, "weekend", "weekday")
    reliable["hod"] = reliable["hour"].dt.hour
    joined = reliable.merge(
        baseline.rename(columns={"hour": "hod"}), on=["site_id", "month", "day_type", "hod"], how="inner"
    )
    for site_id in sorted(recent["site_id"].unique()):
        site = joined[joined["site_id"] == site_id]
        enough = len(site) >= DRIFT_MIN_HOURS
        bias = outlier_share = None
        if enough:
            usual = site[site["avg_kw"] > 0]
            bias = ((usual["consumption_kw"] - usual["avg_kw"]) / usual["avg_kw"]).mean() if len(usual) else None
            spread = site[site["stddev_kw"] > 0]
            if len(spread):
                z = (spread["consumption_kw"] - spread["avg_kw"]).abs() / spread["stddev_kw"]
                outlier_share = (z > DRIFT_OUTLIER_Z).mean()
        window = recent[recent["site_id"] == site_id]
        readings = window["nb_readings"].sum()
        missing = window["nb_missing"].sum() / readings if readings else None
        quality = daily_quality[daily_quality["site_id"] == site_id]
        ratio = None
        if val_nmae and len(quality) >= CONCEPT_MIN_DAYS:
            ratio = quality["nmae"].mean() / val_nmae
        rows += [
            check(checked_at, version, site_id, "level_bias", bias, DRIFT_BIAS_MAX, lambda v: abs(v) > DRIFT_BIAS_MAX),
            check(checked_at, version, site_id, "outlier_share", outlier_share, DRIFT_OUTLIER_SHARE_MAX,
                  lambda v: v > DRIFT_OUTLIER_SHARE_MAX),
            check(checked_at, version, site_id, "missing_share", missing, MISSING_SHARE_MAX,
                  lambda v: v > MISSING_SHARE_MAX),
            check(checked_at, version, site_id, "nmae_ratio", ratio, CONCEPT_NMAE_RATIO_MAX,
                  lambda v: v > CONCEPT_NMAE_RATIO_MAX),
            check(checked_at, version, site_id, "prediction_age_hours", ages.get(site_id),
                  PREDICTION_AGE_MAX_HOURS, lambda v: v > PREDICTION_AGE_MAX_HOURS),
        ]
    return rows


def log_to_mlflow(settings, rows) -> None:
    """Courbes de la surveillance dans l'interface MLflow ; sans effet sur le contrôle si MLflow est injoignable."""
    try:
        mlflow.set_tracking_uri(settings.tracking_uri)
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name="monitor"):
            mlflow.set_tag("model_version", rows[0]["model_version"])
            mlflow.log_metrics(
                {f"{r['metric']}_{r['site_id']}": r["value"] for r in rows if r["value"] is not None}
            )
    except Exception as exc:  # noqa: BLE001 - MLflow est secondaire, la base fait foi
        log.warning("surveillance non enregistrée dans MLflow : %s", type(exc).__name__)


def run(now=None) -> list[dict]:
    """Contrôle le champion et enregistre les résultats ; renvoie les lignes écrites."""
    configure()
    now = (now if now is not None else pd.Timestamp.now(tz="UTC")).floor("h")
    settings = load_settings()
    version = data.champion_version(settings.database_url)
    if version is None:
        raise SystemExit("Aucun modèle champion en base : lancer d'abord l'entraînement.")

    recent = data.load_hourly(
        settings.database_url, start=now - timedelta(days=DRIFT_WINDOW_DAYS), end=now
    )
    if recent.empty:
        raise SystemExit("Aucune mesure sur la fenêtre récente : rien à contrôler.")
    rows = assess(
        recent,
        data.load_baseline(settings.database_url),
        data.load_daily_quality(settings.database_url, version, DRIFT_WINDOW_DAYS),
        data.validation_nmae(settings.database_url, version),
        data.load_prediction_ages(settings.database_url),
        version,
        now,
    )
    data.save_drift_metrics(settings.database_url, rows)
    log_to_mlflow(settings, rows)

    alerts = [r for r in rows if r["status"] == ALERT]
    insufficient = sum(r["status"] == INSUFFICIENT for r in rows)
    log.info("surveillance du champion v%s : %d contrôles, %d alertes, %d sans assez de données",
             version, len(rows), len(alerts), insufficient)
    print(f"Champion v{version} : {len(rows)} contrôles, {len(alerts)} alerte(s), "
          f"{insufficient} sans assez de données")
    for r in alerts:
        print(f"  ALERTE {r['site_id']} {r['metric']} : {r['value']:.3f} (seuil {r['threshold']})")
    return rows


def main() -> None:
    rows = run()
    if any(r["status"] == ALERT for r in rows):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
