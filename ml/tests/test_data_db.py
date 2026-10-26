"""Requêtes de data.py contre TimescaleDB, avec le rôle enervision_ml.

Ignorés sans DATABASE_URL (base migrée par db/migrations). Le site SITE997 est créé puis
supprimé par le test. Les heures sont récentes : l'agrégat horaire les montre sans rafraîchissement
(agrégation en temps réel), et un rafraîchissement ne peut pas se faire dans une transaction.
"""

import os
from datetime import timedelta

import pandas as pd
import psycopg
import pytest

from enervision_ml import data

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL absent : pas de base")

SITE = "SITE997"
HOURS = 3
RUN_VERSION = "test-run"


def as_ml_role(url: str) -> str:
    """La même base, mais les requêtes s'exécutent avec les droits du rôle enervision_ml."""
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-c%20role%3Denervision_ml"


def cleanup(conn) -> None:
    conn.execute("DELETE FROM ml.prediction WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM ml.model_run WHERE model_version = %s", (RUN_VERSION,))
    conn.execute("DELETE FROM core.energy_reading WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM ref.site WHERE site_id = %s", (SITE,))


@pytest.fixture
def seeded():
    """Trois heures pleines de SITE997 : 100, 110 puis 120 kW, dont un relevé sans consommation."""
    first = pd.Timestamp.now(tz="UTC").floor("h") - timedelta(hours=HOURS + 1)
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        cleanup(conn)
        conn.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) "
            "VALUES (%s, 'Site de test', 'office', 500)",
            (SITE,),
        )
        for offset in range(HOURS):
            hour = first + timedelta(hours=offset)
            conn.execute(
                "INSERT INTO core.energy_reading "
                "(time, mock_time, site_id, consumption_kw, temperature_celsius, "
                "data_quality, source) VALUES (%s, %s, %s, %s, 15, 'good', 'readings')",
                (hour, hour, SITE, 100 + 10 * offset),
            )
        conn.execute(
            "INSERT INTO core.energy_reading "
            "(time, mock_time, site_id, consumption_kw, data_quality, source) "
            "VALUES (%s, %s, %s, NULL, 'partial', 'readings')",
            (first + timedelta(minutes=30), first + timedelta(minutes=30), SITE),
        )
        yield first
        cleanup(conn)


def test_load_hourly_reads_the_aggregate_with_the_ml_role(seeded):
    df = data.load_hourly(as_ml_role(DATABASE_URL), start=seeded)
    site = df[df["site_id"] == SITE].sort_values("hour").reset_index(drop=True)

    assert list(site.columns) == data.HOURLY_COLUMNS
    assert len(site) == HOURS
    assert site["site_type"].iloc[0] == "office"
    assert site["capacity_kw"].iloc[0] == 500.0
    assert site["consumption_kw"].tolist() == [100.0, 110.0, 120.0]
    # Le relevé sans consommation de la première heure compte comme manquant
    assert site["nb_readings"].iloc[0] == 2
    assert site["nb_missing"].iloc[0] == 1


def test_load_hourly_end_is_excluded(seeded):
    end = seeded + timedelta(hours=2)
    df = data.load_hourly(as_ml_role(DATABASE_URL), start=seeded, end=end)
    site = df[df["site_id"] == SITE]
    assert site["hour"].max() < end
    assert len(site) == 2


def test_latest_hour_with_the_ml_role(seeded):
    assert data.latest_hour(as_ml_role(DATABASE_URL)) >= seeded + timedelta(hours=HOURS - 1)


def test_save_predictions_updates_instead_of_duplicating(seeded):
    target = seeded + timedelta(hours=HOURS + 1)
    url = as_ml_role(DATABASE_URL)
    first = pd.DataFrame(
        {"target_time": [target], "site_id": [SITE], "predicted_kw": [100.5], "is_peak": [False]}
    )
    again = first.assign(predicted_kw=[101.5], is_peak=[True])

    assert data.save_predictions(url, first, "7") == 1
    assert data.save_predictions(url, again, "7") == 1

    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute(
            "SELECT predicted_kw::float, is_peak FROM ml.prediction WHERE site_id = %s", (SITE,)
        ).fetchall()
    assert rows == [(101.5, True)]


def test_ml_role_cannot_write_measures(seeded):
    with (
        psycopg.connect(as_ml_role(DATABASE_URL)) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(
            "INSERT INTO core.energy_reading (time, mock_time, site_id, data_quality, source) "
            "VALUES (now(), now(), %s, 'good', 'readings')",
            (SITE,),
        )


def model_run(**changes) -> dict:
    run = {
        "model_version": RUN_VERSION,
        "run_id": "run-a",
        "model": "site_profile",
        "train_start": pd.Timestamp("2025-01-01", tz="UTC"),
        "train_end": pd.Timestamp("2026-01-01", tz="UTC"),
        "promoted": True,
        "decision": "promu champion (premier modèle)",
        "shiftable_ratio": 0.1,
        "peak_penalty_eur_kwh": 0.15,
    }
    return {**run, **changes}


def test_save_model_run_is_replayable_with_the_ml_role(seeded):
    url = as_ml_role(DATABASE_URL)
    data.save_model_run(url, model_run(), {"val_nmae": 0.04, "test_nmae": 0.05}, {SITE: 125.0})
    # Le registre MLflow remis à zéro réutilise la version : la ligne est remplacée, pas dupliquée
    data.save_model_run(
        url, model_run(run_id="run-b", promoted=False), {"val_nmae": 0.03}, {SITE: 130.0}
    )

    with psycopg.connect(DATABASE_URL) as conn:
        runs = conn.execute(
            "SELECT run_id, promoted FROM ml.model_run WHERE model_version = %s", (RUN_VERSION,)
        ).fetchall()
        metrics = dict(
            conn.execute(
                "SELECT metric, value FROM ml.model_metric WHERE model_version = %s", (RUN_VERSION,)
            ).fetchall()
        )
        thresholds = conn.execute(
            "SELECT threshold_kw::float FROM ml.peak_threshold WHERE model_version = %s",
            (RUN_VERSION,),
        ).fetchall()
    assert runs == [("run-b", False)]
    assert metrics == {"val_nmae": 0.03, "test_nmae": 0.05}
    assert thresholds == [(130.0,)]


def test_save_model_run_writes_nothing_when_a_table_fails(seeded):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        data.save_model_run(
            as_ml_role(DATABASE_URL), model_run(), {"val_nmae": 0.04}, {"SITE_INCONNU": 1.0}
        )

    with psycopg.connect(DATABASE_URL) as conn:
        count = conn.execute(
            "SELECT count(*) FROM ml.model_run WHERE model_version = %s", (RUN_VERSION,)
        ).fetchone()[0]
    assert count == 0
