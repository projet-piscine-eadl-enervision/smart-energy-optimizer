"""monitor.run : orchestration avec une base simulée."""
import pandas as pd
import pytest

from enervision_ml import monitor
from tests.test_monitor import NOW, baseline, daily, recent


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///:memory:")
    saved = []
    monkeypatch.setattr(monitor.data, "champion_version", lambda url: "1")
    monkeypatch.setattr(monitor.data, "load_hourly", lambda url, start=None, end=None: recent())
    monkeypatch.setattr(monitor.data, "load_baseline", lambda url: baseline())
    monkeypatch.setattr(monitor.data, "load_daily_quality", lambda url, version, days: daily(0.04))
    monkeypatch.setattr(monitor.data, "validation_nmae", lambda url, version: 0.04)
    monkeypatch.setattr(monitor.data, "load_prediction_ages", lambda url: {"SITE001": 0.5})
    monkeypatch.setattr(monitor.data, "save_drift_metrics", lambda url, rows: saved.append(rows) or len(rows))
    monkeypatch.setattr(monitor, "log_to_mlflow", lambda settings, rows: None)
    return saved


def test_run_saves_the_checks_and_reports(wired, capsys):
    rows = monitor.run(now=NOW)

    assert wired == [rows]
    assert "0 alerte(s)" in capsys.readouterr().out


def test_main_exits_with_2_on_an_alert(wired, monkeypatch):
    monkeypatch.setattr(monitor.data, "load_hourly", lambda url, start=None, end=None: recent(shift=0.3))

    with pytest.raises(SystemExit) as exit_info:
        monitor.main()

    assert exit_info.value.code == 2
    assert wired  # les résultats sont écrits avant la sortie en erreur


def test_run_without_champion_stops(wired, monkeypatch):
    monkeypatch.setattr(monitor.data, "champion_version", lambda url: None)

    with pytest.raises(SystemExit, match="Aucun modèle champion"):
        monitor.run(now=NOW)


def test_mlflow_failure_does_not_stop_the_check(monkeypatch):
    class Settings:
        tracking_uri = "http://injoignable.invalid:5000"

    monkeypatch.setattr(monitor.mlflow, "set_experiment", lambda name: (_ for _ in ()).throw(OSError("injoignable")))

    monitor.log_to_mlflow(Settings(), [{"model_version": "1", "metric": "m", "site_id": "S", "value": 1.0}])


def test_a_site_summary_is_logged(wired, caplog):
    caplog.set_level("INFO")

    monitor.run(now=pd.Timestamp(NOW))

    assert any("surveillance du champion v1" in r.message for r in caplog.records)
