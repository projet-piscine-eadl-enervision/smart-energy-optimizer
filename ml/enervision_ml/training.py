"""Entraînement : évalue un challenger, l'enregistre et le promeut s'il bat le champion.

Lancement manuel :
    docker compose run --rm ml                                  # SiteProfile, par défaut
    docker compose run --rm ml python train.py --model seasonal_naive
"""

import argparse
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.models import infer_signature

from enervision_ml import registry
from enervision_ml.config import (
    CALENDAR_TZ,
    EXPERIMENT,
    HORIZON_HOURS,
    MAX_MISSING_RATIO,
    MIN_TRAIN_DAYS,
    MODEL_NAME,
    PEAK_PENALTY_EUR_KWH,
    PEAK_RATIO,
    SHIFTABLE_RATIO,
    TEST_DAYS,
    VALIDATION_DAYS,
    load_settings,
)
from enervision_ml.data import load_hourly, save_model_run
from enervision_ml.evaluate import evaluate, temporal_split
from enervision_ml.features import (
    FEATURE_COLUMNS,
    add_features,
    mask_unreliable_hours,
    to_hourly_grid,
)
from enervision_ml.models import (
    MODELS,
    ConsumptionModel,
    SeasonalNaive,
    peak_thresholds,
)

MODEL_INPUT_COLUMNS = ["site_id", *FEATURE_COLUMNS]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Entraîne un challenger.")
    parser.add_argument("--model", choices=sorted(MODELS), default="site_profile")
    args = parser.parse_args(argv)

    settings = load_settings()
    mlflow.set_tracking_uri(settings.tracking_uri)
    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()

    # ML_DATA_END fige la fin du jeu : les fenêtres de découpage ne glissent plus
    # quand le collecteur ajoute des heures
    raw = load_hourly(settings.database_url, end=settings.data_end)
    if raw.empty:
        raise SystemExit(
            "analytics.energy_hourly est vide : l'ETL (ou scripts/seed_dev.py en local) "
            "doit d'abord charger des mesures."
        )
    data = add_features(to_hourly_grid(mask_unreliable_hours(raw)))
    train, validation, test = temporal_split(data)
    train_days = (train["hour"].max() - train["hour"].min()).days if len(train) else 0
    if train_days < MIN_TRAIN_DAYS:
        raise SystemExit(
            f"Historique insuffisant : {train_days} jours d'entraînement pour {MIN_TRAIN_DAYS} "
            f"requis (plus {VALIDATION_DAYS + TEST_DAYS} jours de validation et de test). "
            "Le facteur du mois demande au moins un an."
        )

    estimator = MODELS[args.model]().fit(train)
    model = ConsumptionModel(estimator, peak_thresholds(train))
    validation_input = validation[MODEL_INPUT_COLUMNS]
    validation_output = model.predict(None, validation_input)

    with mlflow.start_run(run_name=estimator.name) as run:
        mlflow.log_params(
            {
                "model": estimator.name,
                "code_version": settings.code_version,
                "horizon_hours": HORIZON_HOURS,
                "calendar_tz": CALENDAR_TZ,
                "peak_ratio": PEAK_RATIO,
                "max_missing_ratio": MAX_MISSING_RATIO,
                "shiftable_ratio": SHIFTABLE_RATIO,
                "peak_penalty_eur_kwh": PEAK_PENALTY_EUR_KWH,
                "validation_days": VALIDATION_DAYS,
                "test_days": TEST_DAYS,
                "train_period": f"{train['hour'].min()} → {train['hour'].max()}",
                "validation_period": f"{validation['hour'].min()} → {validation['hour'].max()}",
                "test_period": f"{test['hour'].min()} → {test['hour'].max()}",
            }
        )
        validation_metrics = evaluate(
            validation, validation_output["predicted_kw"], model.thresholds
        )
        test_output = model.predict(None, test[MODEL_INPUT_COLUMNS])
        test_metrics = evaluate(test, test_output["predicted_kw"], model.thresholds)
        metrics = {
            **{f"val_{k}": v for k, v in validation_metrics.items()},
            **{f"test_{k}": v for k, v in test_metrics.items()},
            **gain_vs_naive(train, test, test_metrics, model.thresholds),
        }
        mlflow.log_metrics(metrics)
        mlflow.log_dict(model.thresholds, "peak_thresholds.json")
        # Empreinte des données de chaque période : une version se rattache aux données exactes
        # qui l'ont produite, et deux runs sur les mêmes données ont la même empreinte
        for context, period in (("training", train), ("validation", validation), ("test", test)):
            mlflow.log_input(
                mlflow.data.from_pandas(
                    period[["hour", "site_id", "consumption_kw"]],
                    name=f"energy_hourly_{context}",
                    targets="consumption_kw",
                ),
                context=context,
            )

        info = mlflow.pyfunc.log_model(
            name="model",
            python_model=model,
            # Embarque le code du package : le modèle se recharge sans dépendre de l'image
            code_paths=[str(Path(__file__).parent)],
            signature=infer_signature(validation_input, validation_output),
            registered_model_name=MODEL_NAME,
        )

    version = str(info.registered_model_version)
    registry.set_alias(client, registry.CHALLENGER, version)
    decision = promote_if_better(client, version, validation, validation_metrics["nmae"])
    client.set_tag(run.info.run_id, "decision", decision)
    # Copie en base pour le suivi en SQL (vues ml.prediction_*, Grafana)
    save_model_run(
        settings.database_url,
        {
            "model_version": version,
            "run_id": run.info.run_id,
            "model": estimator.name,
            "train_start": train["hour"].min(),
            "train_end": train["hour"].max(),
            "promoted": str(registry.get_alias(client, registry.CHAMPION).version) == version,
            "decision": decision,
            "shiftable_ratio": SHIFTABLE_RATIO,
            "peak_penalty_eur_kwh": PEAK_PENALTY_EUR_KWH,
        },
        metrics,
        model.thresholds,
    )

    print(f"Run {run.info.run_id} : {MODEL_NAME} v{version} ({estimator.name})")
    print(f"  validation : nMAE {validation_metrics['nmae']:.3f}, MAE {validation_metrics['mae']:.1f} kW")
    print(f"  test       : nMAE {test_metrics['nmae']:.3f}, MAE {test_metrics['mae']:.1f} kW")
    print(
        f"  impact     : {test_metrics['kpi_peak_kwh_avoided']:.0f} kWh de dépassement évités "
        f"({test_metrics['kpi_peak_avoided_ratio']:.0%} du maximum), "
        f"{test_metrics['kpi_penalty_saved_eur']:.0f} € sur le test"
    )
    print(f"  décision   : {decision}")


def gain_vs_naive(train, test, test_metrics: dict[str, float], thresholds) -> dict[str, float]:
    """Compare au modèle naïf sur le même test : ce que le modèle apporte en plus.

    test_nmae_gain_vs_naive : baisse relative de l'erreur (0,3 = 30 % d'erreur en moins).
    test_kpi_penalty_gain_vs_naive_eur : dépassement facturé évité en plus du naïf.
    """
    naive = ConsumptionModel(SeasonalNaive().fit(train), thresholds)
    naive_output = naive.predict(None, test[MODEL_INPUT_COLUMNS])
    naive_metrics = evaluate(test, naive_output["predicted_kw"], thresholds)
    return {
        "test_naive_nmae": naive_metrics["nmae"],
        "test_naive_peak_f1": naive_metrics["peak_f1"],
        "test_naive_kpi_penalty_saved_eur": naive_metrics["kpi_penalty_saved_eur"],
        "test_nmae_gain_vs_naive": 1 - test_metrics["nmae"] / naive_metrics["nmae"],
        "test_kpi_penalty_gain_vs_naive_eur": (
            test_metrics["kpi_penalty_saved_eur"] - naive_metrics["kpi_penalty_saved_eur"]
        ),
    }


def promote_if_better(client: MlflowClient, version: str, validation, challenger_nmae: float) -> str:
    """Compare au champion sur la validation actuelle, pas sur ses anciens chiffres.

    Les données s'enrichissent avec le temps : réévaluer le champion sur la même période
    est la seule comparaison équitable.
    """
    champion = registry.get_alias(client, registry.CHAMPION)
    if champion is None:
        registry.set_alias(client, registry.CHAMPION, version)
        return f"v{version} promu champion (premier modèle)"

    champion_model = registry.load_model(champion.version)
    champion_output = champion_model.predict(validation[MODEL_INPUT_COLUMNS])
    thresholds = champion_model.unwrap_python_model().thresholds
    champion_nmae = evaluate(validation, champion_output["predicted_kw"], thresholds)["nmae"]

    if challenger_nmae < champion_nmae:
        registry.set_alias(client, registry.CHAMPION, version)
        return (
            f"v{version} promu champion : nMAE {challenger_nmae:.3f} "
            f"< {champion_nmae:.3f} (v{champion.version})"
        )
    return (
        f"v{version} reste challenger : nMAE {challenger_nmae:.3f} "
        f">= {champion_nmae:.3f} (champion v{champion.version})"
    )
