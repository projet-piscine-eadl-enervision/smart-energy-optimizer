from datetime import UTC, datetime

import pandas as pd
import pytest

from enervision_ml.config import load_settings, parse_data_end
from enervision_ml.predict import check_fresh


def test_data_end_empty_means_midnight_utc_today():
    now = datetime(2026, 10, 26, 16, 50, tzinfo=UTC)
    expected = datetime(2026, 10, 26, tzinfo=UTC)
    assert parse_data_end(None, now) == expected
    assert parse_data_end("", now) == expected


def test_data_end_default_is_stable_within_a_day():
    morning = datetime(2026, 10, 26, 0, 5, tzinfo=UTC)
    evening = datetime(2026, 10, 26, 23, 55, tzinfo=UTC)
    assert parse_data_end(None, morning) == parse_data_end(None, evening)


def test_data_end_defaults_to_utc():
    assert parse_data_end("2025-05-15") == datetime(2025, 5, 15, tzinfo=UTC)


def test_fresh_data_is_accepted():
    now = pd.Timestamp("2026-10-26 12:00", tz="UTC")
    check_fresh(pd.Timestamp("2026-10-26 10:00", tz="UTC"), now)


def test_stale_data_is_refused():
    now = pd.Timestamp("2026-10-26 12:00", tz="UTC")
    with pytest.raises(SystemExit, match="5 h de retard"):
        check_fresh(pd.Timestamp("2026-10-26 07:00", tz="UTC"), now)


def test_public_url_is_none_in_production(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("MLFLOW_PUBLIC_URL", "http://localhost:5001")
    assert load_settings().public_url is None


def test_public_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.setenv("MLFLOW_PUBLIC_URL", "http://localhost:5001")
    assert load_settings().public_url == "http://localhost:5001"


def test_public_url_defaults_to_the_tracking_uri(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://non-utilisee")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    monkeypatch.delenv("MLFLOW_PUBLIC_URL", raising=False)
    assert load_settings().public_url == "http://mlflow:5000"
