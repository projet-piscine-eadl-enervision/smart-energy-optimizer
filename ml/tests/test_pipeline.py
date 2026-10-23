"""Bout en bout sans base ni serveur : MLflow dans un fichier SQLite temporaire, et des
données factices à la place de analytics.energy_hourly."""

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
    monkeypatch.setattr(training, "load_hourly", lambda url, start=None: data)
    return data


def test_le_naif_ne_detrone_pas_le_profil(pipeline):
    training.main(["--model", "site_profile"])
    training.main(["--model", "seasonal_naive"])

    client = MlflowClient()
    assert str(registry.get_alias(client, registry.CHAMPION).version) == "1"
    assert str(registry.get_alias(client, registry.CHALLENGER).version) == "2"
    assert "promu champion (premier modèle)" in decision(client, "1")
    assert "reste challenger" in decision(client, "2")


def test_un_meilleur_modele_est_promu(pipeline):
    training.main(["--model", "seasonal_naive"])
    training.main(["--model", "site_profile"])

    client = MlflowClient()
    assert str(registry.get_alias(client, registry.CHAMPION).version) == "2"
    assert "promu champion : nMAE" in decision(client, "2")


def test_historique_insuffisant(pipeline, monkeypatch):
    short = make_mock_like(days=200)
    monkeypatch.setattr(training, "load_hourly", lambda url, start=None: short)
    with pytest.raises(SystemExit, match="Historique insuffisant"):
        training.main([])


def test_prediction_avec_le_champion(pipeline, monkeypatch):
    training.main([])

    saved = {}

    def fake_save(url, predictions, version):
        saved.update(predictions=predictions, version=version)
        return len(predictions)

    monkeypatch.setattr(predict, "latest_hour", lambda url: pipeline["hour"].max())
    monkeypatch.setattr(
        predict, "load_hourly", lambda url, start=None: pipeline[pipeline["hour"] >= start]
    )
    monkeypatch.setattr(predict, "save_predictions", fake_save)

    count = predict.run()

    sites = pipeline["site_id"].nunique()
    assert count == HORIZON_HOURS * sites
    assert saved["version"] == "1"
    predictions = saved["predictions"]
    assert (predictions["target_time"] > pipeline["hour"].max()).all()
    assert predictions["predicted_kw"].notna().all()
    # Profil de bureau : pics de demande en journée de semaine uniquement
    peak_hours = predictions.loc[predictions["is_peak"], "target_time"].dt.hour
    assert peak_hours.between(8, 18).all()


def test_prediction_sans_champion(pipeline):
    with pytest.raises(SystemExit, match="Aucun modèle champion"):
        predict.run()
