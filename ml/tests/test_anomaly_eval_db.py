"""Lecture de ml.history_labeled avec le rôle ML. Ignoré sans DATABASE_URL.

Le site SITE994 est créé puis supprimé par le test. L'ETL charge cette table en production
(traitement load-history) ; le test la remplit lui-même.
"""
import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from enervision_ml import data

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL absent : pas de base")

SITE = "SITE994"


def as_ml_role(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-c%20role%3Denervision_ml"


def cleanup(conn) -> None:
    conn.execute("DELETE FROM ml.history_labeled WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM ref.site WHERE site_id = %s", (SITE,))


@pytest.fixture
def seeded():
    start = datetime(2024, 1, 1, tzinfo=UTC)
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        cleanup(conn)
        conn.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) VALUES (%s, 'Site de test', 'office', 500)",
            (SITE,),
        )
        rows = [
            (SITE, start + timedelta(hours=0), 100.0, "measured", None, None),
            (SITE, start + timedelta(hours=1), 210.0, "measured", "spike", "high"),
            (SITE, start + timedelta(hours=2), None, "missing", None, None),
        ]
        for site, time, kw, source, anomaly, severity in rows:
            conn.execute(
                "INSERT INTO ml.history_labeled (site_id, time, consumption_kw, consumption_source, anomaly_type, anomaly_severity) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (site, time, kw, source, anomaly, severity),
            )
        yield
        cleanup(conn)


def test_labeled_history_is_read_with_the_ml_role_without_missing_hours(seeded):
    frame = data.load_labeled_history(as_ml_role(DATABASE_URL))
    site = frame[frame["site_id"] == SITE]

    assert list(site["consumption_kw"]) == [100.0, 210.0]
    assert site["anomaly_type"].isna().tolist() == [True, False]
    assert site["anomaly_type"].iloc[1] == "spike"
