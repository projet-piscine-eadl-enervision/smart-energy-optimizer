"""ml.drift_metric, ml.model_health et ml.model_status contre TimescaleDB migrée, avec le rôle ML.

Ignorés sans DATABASE_URL. Le site SITE995 et la version drift-test sont créés puis supprimés par le test.
"""
import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from enervision_ml import data

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL absent : pas de base")

SITE = "SITE995"
VERSION = "drift-test"


def as_ml_role(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-c%20role%3Denervision_ml"


def cleanup(conn) -> None:
    conn.execute("DELETE FROM ml.prediction WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM ml.model_run WHERE model_version = %s", (VERSION,))  # supprime aussi ses contrôles
    conn.execute("DELETE FROM ref.site WHERE site_id = %s", (SITE,))


def row(checked_at, metric, value, status, threshold=1.0):
    return {"checked_at": checked_at, "model_version": VERSION, "site_id": SITE, "metric": metric,
            "value": value, "threshold": threshold, "status": status}


@pytest.fixture
def seeded():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        cleanup(conn)
        conn.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) VALUES (%s, 'Site de test', 'office', 500)",
            (SITE,),
        )
        conn.execute(
            "INSERT INTO ml.model_run (model_version, run_id, model, train_start, train_end, data_end, promoted, "
            "decision, shiftable_ratio, peak_penalty_eur_kwh, is_champion) "
            "VALUES (%s, 'run', 'site_profile', now(), now(), now(), true, 'test', 0.1, 0.15, false)",
            (VERSION,),
        )
        yield
        cleanup(conn)


def health(conn):
    return conn.execute(
        "SELECT metric, status FROM ml.model_health WHERE site_id = %s ORDER BY metric", (SITE,)
    ).fetchall()


def test_drift_metrics_are_written_with_the_ml_role_and_replayable(seeded):
    t = datetime.now(UTC).replace(microsecond=0)
    url = as_ml_role(DATABASE_URL)

    assert data.save_drift_metrics(url, [row(t, "level_bias", 0.02, "ok"), row(t, "nmae_ratio", None, "insufficient")]) == 2
    data.save_drift_metrics(url, [row(t, "level_bias", 0.15, "alert")])  # même instant : mis à jour

    with psycopg.connect(DATABASE_URL) as conn:
        assert health(conn) == [("level_bias", "alert"), ("nmae_ratio", "insufficient")]


def test_the_latest_check_wins_in_the_health_view(seeded):
    t = datetime.now(UTC).replace(microsecond=0)
    url = as_ml_role(DATABASE_URL)
    data.save_drift_metrics(url, [row(t - timedelta(days=1), "level_bias", 0.2, "alert")])
    data.save_drift_metrics(url, [row(t, "level_bias", 0.01, "ok")])

    with psycopg.connect(DATABASE_URL) as conn:
        assert health(conn) == [("level_bias", "ok")]


def test_the_status_view_summarises_alerts(seeded):
    t = datetime.now(UTC).replace(microsecond=0)
    data.save_drift_metrics(as_ml_role(DATABASE_URL), [row(t, "level_bias", 0.2, "alert"), row(t, "missing_share", 0.0, "ok")])

    with psycopg.connect(DATABASE_URL) as conn:
        status, alerts = conn.execute(
            "SELECT status, nb_alerts FROM ml.model_status"
        ).fetchone()
    # La vue regarde tous les sites : au moins notre alerte
    assert status == "alert"
    assert alerts >= 1


def test_the_read_functions_work_with_the_ml_role(seeded):
    url = as_ml_role(DATABASE_URL)

    assert data.champion_version(url) is None or isinstance(data.champion_version(url), str)
    assert data.validation_nmae(url, VERSION) is None
    assert list(data.load_baseline(url).columns) == ["site_id", "month", "day_type", "hour", "avg_kw", "stddev_kw"]
    assert list(data.load_daily_quality(url, VERSION, 7).columns) == ["day", "site_id", "nmae"]
    assert isinstance(data.load_prediction_ages(url), dict)


def test_operation_views_cover_the_next_24_hours(seeded):
    hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        for n in range(1, 7):
            conn.execute(
                "INSERT INTO ml.prediction (target_time, site_id, model_version, predicted_kw, is_peak) "
                "VALUES (%s, %s, %s, 100, false)",
                (hour + timedelta(hours=n), SITE, VERSION),
            )
        coverage = conn.execute(
            "SELECT coverage_next_24h FROM ml.forecast_coverage WHERE site_id = %s", (SITE,)
        ).fetchone()[0]
        kpi_rows = conn.execute("SELECT count(*) FROM ml.operation_kpi").fetchone()[0]

    assert coverage == pytest.approx(6 / 24)
    assert kpi_rows >= 0  # la vue répond ; elle se remplit avec les prévisions comparées aux mesures
