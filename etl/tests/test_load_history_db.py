"""Chargement de l'historique sur une vraie base migrée. Ignoré sans DATABASE_URL.

Local : docker compose up -d db && docker compose run --rm migrate, puis
DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision python -m pytest tests/test_load_history_db.py
Tout est annulé à la fin de chaque test (transaction abandonnée).
"""
import os

import psycopg
import pytest

from pipeline import db
from pipeline.jobs import load_history
from tests.test_load_history import history, save

# Identifiant propre au test : la base peut déjà contenir les vrais sites
SITE = "SITE997"

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL absent")


@pytest.fixture
def conn():
    with db.connect() as connection, connection.transaction(force_rollback=True):
        connection.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, location, capacity_kw, status)"
            " VALUES (%s, 'test', 'office', 'test', 100, 'active') ON CONFLICT DO NOTHING",
            (SITE,),
        )
        yield connection


def table(conn):
    return conn.execute(
        "SELECT time, consumption_kw, consumption_source, anomaly_type, anomaly_severity"
        " FROM ml.history_labeled WHERE site_id = %s ORDER BY time",
        (SITE,),
    ).fetchall()


def test_load_is_idempotent_and_never_stores_nan(conn, tmp_path):
    path = save(tmp_path, history({"site_id": SITE}))

    assert load_history.run(conn, path) == (4, 0)
    assert load_history.run(conn, path) == (0, 0)  # même fichier : rien ne change

    rows = table(conn)
    assert [row[1] for row in rows] == [100.5, None, 90.0, 95.25]
    assert (rows[2][3], rows[2][4]) == ("spike", "high")
    nan_count = conn.execute(
        "SELECT count(*) FROM ml.history_labeled WHERE site_id = %s AND ("
        " consumption_kw = 'NaN' OR temperature_celsius = 'NaN' OR humidity_percent = 'NaN')",
        (SITE,),
    ).fetchone()[0]
    assert nan_count == 0

    statuses = conn.execute(
        "SELECT status, rows_loaded, rows_rejected FROM etl.run WHERE run_type = 'history_load' ORDER BY run_id"
    ).fetchall()
    assert statuses[-2:] == [("success", 4, 0), ("success", 0, 0)]


def test_a_corrected_file_updates_only_the_changed_rows(conn, tmp_path):
    load_history.run(conn, save(tmp_path, history({"site_id": SITE})))
    corrected = history({"site_id": SITE, "consumption_kwh_clean": [100.5, 80.0, 90.0, 95.25],
                         "consumption_kwh_source": ["measured", "interpolated", "interpolated", "recovered_from_euros"]})

    assert load_history.run(conn, save(tmp_path, corrected)) == (1, 0)
    assert table(conn)[1][1:3] == (80.0, "interpolated")


def test_the_database_refuses_what_the_loader_would_let_through(conn):
    with pytest.raises(psycopg.errors.ForeignKeyViolation, match="anomaly_type"):
        conn.execute(
            "INSERT INTO ml.history_labeled (site_id, time, consumption_source, anomaly_type, anomaly_severity)"
            " VALUES (%s, now(), 'measured', 'inconnu', 'high')", (SITE,),
        )
