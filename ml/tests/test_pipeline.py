"""Bout en bout sans base ni serveur : MLflow dans un fichier SQLite temporaire, et des
données factices à la place de analytics.energy_hourly."""

from datetime import UTC, datetime, time

import pandas as pd
import psycopg
import pytest
from mlflow import MlflowClient

from enervision_ml import predict, registry, training
from enervision_ml.config import HORIZON_HOURS, MODEL_NAME
from tests.conftest import make_mock_like


def decision(client: MlflowClient, version: str) -> str:
    run_id = client.get_model_version(MODEL_NAME, version).run_id
    return client.get_run(run_id).data.tags["decision"]


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # les artefacts MLflow vont dans le dossier temporaire
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")

    # Un an d'entraînement, plus 60 jours de validation et 60 de test
    data = make_mock_like(days=500)
    monkeypatch.setattr(training, "load_hourly", lambda url, start=None, end=None: data)
    monkeypatch.setattr(training, "save_model_run", lambda url, run, metrics, thresholds: None)
    return data


def test_naive_does_not_dethrone_profile(pipeline):
    training.main(["--model", "site_profile"])
    training.main(["--model", "seasonal_naive"])

    client = MlflowClient()
    assert str(registry.get_alias(client, registry.CHAMPION).version) == "1"
    assert str(registry.get_alias(client, registry.CHALLENGER).version) == "2"
    assert "promu champion (premier modèle)" in decision(client, "1")
    assert "reste challenger" in decision(client, "2")


def test_better_model_is_promoted(pipeline):
    training.main(["--model", "seasonal_naive"])
    training.main(["--model", "site_profile"])

    client = MlflowClient()
    assert str(registry.get_alias(client, registry.CHAMPION).version) == "2"
    assert "promu champion : nMAE" in decision(client, "2")


def test_insufficient_history(pipeline, monkeypatch):
    short = make_mock_like(days=200)
    monkeypatch.setattr(training, "load_hourly", lambda url, start=None, end=None: short)
    with pytest.raises(SystemExit, match="Historique insuffisant"):
        training.main([])


def test_prediction_with_champion(pipeline, monkeypatch):
    training.main([])

    saved = {}

    def fake_save(url, predictions, version):
        saved.update(predictions=predictions, version=version)
        return len(predictions)

    monkeypatch.setattr(predict, "latest_hour", lambda url: pipeline["hour"].max())
    monkeypatch.setattr(
        predict, "load_hourly", lambda url, start=None, end=None: pipeline[pipeline["hour"] >= start]
    )
    monkeypatch.setattr(predict, "save_predictions", fake_save)
    monkeypatch.setattr(predict, "refresh_recommendations", lambda url: 0)

    count = predict.run(now=pipeline["hour"].max() + pd.Timedelta(hours=1))

    sites = pipeline["site_id"].nunique()
    assert count == HORIZON_HOURS * sites
    assert saved["version"] == "1"
    predictions = saved["predictions"]
    assert (predictions["target_time"] > pipeline["hour"].max()).all()
    assert predictions["predicted_kw"].notna().all()
    # Profil de bureau : pics de demande en journée de semaine uniquement
    peak_hours = predictions.loc[predictions["is_peak"], "target_time"].dt.hour
    assert peak_hours.between(8, 18).all()


def test_prediction_without_champion(pipeline):
    with pytest.raises(SystemExit, match="Aucun modèle champion"):
        predict.run()


def test_impact_and_data_recorded_in_mlflow(pipeline):
    training.main(["--model", "site_profile"])

    client = MlflowClient()
    run = client.get_run(client.get_model_version(MODEL_NAME, "1").run_id)
    metrics = run.data.metrics
    # Le profil se trompe moins que le naïf. Sur un mock, les pics de bureau dépassent le seuil
    # de loin : les deux les annoncent tous, et évitent le même dépassement
    assert metrics["test_nmae_gain_vs_naive"] > 0.2
    assert metrics["test_kpi_penalty_gain_vs_naive_eur"] == 0
    assert metrics["test_kpi_peak_avoided_ratio"] == 1
    assert metrics["test_kpi_penalty_saved_eur"] > 0
    # Chaque période est rattachée au run par l'empreinte de ses données
    contexts = {
        tag.value
        for dataset_input in run.inputs.dataset_inputs
        for tag in dataset_input.tags
        if tag.key == "mlflow.data.context"
    }
    assert contexts == {"training", "validation", "test"}


def test_training_copies_run_to_database(pipeline, monkeypatch):
    saved = []
    monkeypatch.setattr(
        training,
        "save_model_run",
        lambda url, run, metrics, thresholds: saved.append((run, metrics, thresholds)),
    )
    training.main(["--model", "site_profile"])
    training.main(["--model", "seasonal_naive"])

    (first, metrics, thresholds), (second, _, _) = saved
    assert (first["model_version"], first["promoted"], first["champion_version"]) == ("1", True, "1")
    # Le naïf ne détrône pas le profil : la version 1 reste en service
    assert (second["model_version"], second["promoted"], second["champion_version"]) == (
        "2",
        False,
        "1",
    )
    assert {"val_nmae", "test_kpi_penalty_saved_eur", "test_nmae_gain_vs_naive"} <= metrics.keys()
    assert set(thresholds) == set(pipeline["site_id"])


def test_prediction_refused_when_data_is_stale(pipeline, monkeypatch):
    training.main([])
    monkeypatch.setattr(predict, "latest_hour", lambda url: pipeline["hour"].max())
    monkeypatch.setattr(
        predict, "save_predictions", lambda *args: pytest.fail("rien ne doit être écrit")
    )

    with pytest.raises(SystemExit, match="Données trop anciennes"):
        predict.run(now=pipeline["hour"].max() + pd.Timedelta(hours=10))


def test_data_end_is_passed_to_the_query(pipeline, monkeypatch):
    seen = {}

    def fake_load(url, start=None, end=None):
        seen["end"] = end
        return pipeline

    monkeypatch.setattr(training, "load_hourly", fake_load)
    monkeypatch.setenv("ML_DATA_END", "2025-05-15")
    training.main([])
    assert seen["end"] == datetime(2025, 5, 15, tzinfo=UTC)


def test_data_end_defaults_to_midnight_today(pipeline, monkeypatch):
    seen = {}

    def fake_load(url, start=None, end=None):
        seen["end"] = end
        return pipeline

    monkeypatch.setattr(training, "load_hourly", fake_load)
    monkeypatch.delenv("ML_DATA_END", raising=False)
    training.main([])
    assert seen["end"] == datetime.combine(datetime.now(UTC).date(), time.min, tzinfo=UTC)


def test_training_prints_a_link_to_the_run(pipeline, monkeypatch, capsys):
    monkeypatch.setenv("MLFLOW_PUBLIC_URL", "http://localhost:5001/")
    training.main(["--model", "site_profile"])

    run_id = MlflowClient().get_model_version(MODEL_NAME, "1").run_id
    assert "lien MLflow : http://localhost:5001/#/experiments/" in capsys.readouterr().out
    assert training.run_url("http://localhost:5001/", "1", run_id) == (
        f"http://localhost:5001/#/experiments/1/runs/{run_id}"
    )


def test_training_prints_a_link_without_public_url(pipeline, monkeypatch, capsys):
    monkeypatch.delenv("MLFLOW_PUBLIC_URL", raising=False)
    training.main(["--model", "site_profile"])

    assert "lien MLflow : sqlite:///" in capsys.readouterr().out


def test_training_prints_no_link_in_production(pipeline, monkeypatch, capsys):
    monkeypatch.setenv("APP_ENV", "production")
    training.main(["--model", "site_profile"])

    assert "lien MLflow" not in capsys.readouterr().out


def prepare_prediction(pipeline, monkeypatch):
    training.main([])
    monkeypatch.setattr(predict, "latest_hour", lambda url: pipeline["hour"].max())
    monkeypatch.setattr(
        predict, "load_hourly", lambda url, start=None, end=None: pipeline[pipeline["hour"] >= start]
    )
    monkeypatch.setattr(predict, "save_predictions", lambda url, predictions, version: len(predictions))
    return pipeline["hour"].max() + pd.Timedelta(hours=1)


def test_prediction_refreshes_recommendations_after_saving(pipeline, monkeypatch, capsys):
    now = prepare_prediction(pipeline, monkeypatch)
    calls = []
    monkeypatch.setattr(predict, "refresh_recommendations", lambda url: calls.append(url) or 3)

    predict.run(now=now)

    assert calls == ["postgresql://non-utilisee"]
    assert "3 recommandation(s) créée(s)" in capsys.readouterr().out


def test_prediction_fails_visibly_when_recommendations_fail(pipeline, monkeypatch):
    now = prepare_prediction(pipeline, monkeypatch)

    def failing(url):
        raise psycopg.OperationalError("base injoignable")

    monkeypatch.setattr(predict, "refresh_recommendations", failing)

    with pytest.raises(SystemExit, match="Prédictions écrites, mais recommandations non recalculées"):
        predict.run(now=now)
