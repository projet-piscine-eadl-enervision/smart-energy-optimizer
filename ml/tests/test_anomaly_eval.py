"""Évaluation de la détection d'anomalies : fonction pure sur un historique synthétique, et exécution."""
import numpy as np
import pandas as pd
import pytest

from enervision_ml import anomaly_eval


def history(days=120, seed=0):
    """Un site de bureau : 100 kW la journée de semaine, 50 la nuit, bruit de 2 %, avec des anomalies étiquetées."""
    rng = np.random.default_rng(seed)
    hours = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    base = np.where((hours.hour >= 8) & (hours.hour < 19) & (hours.dayofweek < 5), 100.0, 50.0)
    frame = pd.DataFrame(
        {"site_id": "SITE001", "time": hours, "consumption_kw": base * (1 + 0.02 * rng.standard_normal(len(hours))),
         "anomaly_type": None}
    )
    # 40 pics (+100 %) et 40 chutes (-70 %), à des heures de semaine tirées au hasard
    candidates = frame.index[(hours.hour >= 8) & (hours.hour < 19) & (hours.dayofweek < 5)]
    picked = rng.choice(candidates, size=80, replace=False)
    frame.loc[picked[:40], "consumption_kw"] *= 2.0
    frame.loc[picked[:40], "anomaly_type"] = "spike"
    frame.loc[picked[40:], "consumption_kw"] *= 0.3
    frame.loc[picked[40:], "anomaly_type"] = "drop"
    return frame


def test_profile_detector_finds_labeled_spikes_and_drops():
    metrics = anomaly_eval.evaluate(history())

    assert metrics["profile_recall_spike"] > 0.95
    assert metrics["profile_recall_drop"] > 0.95
    assert metrics["profile_flag_precision"] > 0.9
    assert metrics["profile_flag_false_alarm_rate"] < 0.01


def test_peak_rule_finds_spikes_on_the_busy_hours():
    metrics = anomaly_eval.evaluate(history())

    # Une heure ouvrée à 200 kW dépasse 1,25 fois la moyenne du site ; une chute non
    assert metrics["peak_rule_recall_spike_plateau"] > 0.95
    assert "peak_flag_false_alarm_rate" in metrics


def test_an_empty_history_asks_for_the_etl(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setattr(anomaly_eval.data, "load_labeled_history", lambda url: pd.DataFrame(
        columns=["site_id", "time", "consumption_kw", "anomaly_type"]))

    with pytest.raises(SystemExit, match="load-history"):
        anomaly_eval.run()


def test_run_logs_the_metrics(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(anomaly_eval.data, "load_labeled_history", lambda url: history())

    metrics = anomaly_eval.run()

    assert metrics["labeled_hours"] == 80
    assert "profile_recall_spike" in capsys.readouterr().out
