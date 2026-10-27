"""app.refresh_recommendations() contre TimescaleDB migrée, avec le rôle enervision_ml.

Ignorés sans DATABASE_URL (base migrée par db/migrations). Le site SITE996 (un bureau) est créé puis
supprimé par le test. Le test passe par le rôle ML : c'est lui qui prouve que l'appel marche sans droit
d'écriture sur le schéma app.
"""
import os
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL absent : pas de base")

SITE = "SITE996"
VERSION = "rec-test"


def as_ml_role(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}options=-c%20role%3Denervision_ml"


def cleanup(conn) -> None:
    conn.execute("DELETE FROM app.recommendation WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM core.alert WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM ml.prediction WHERE site_id = %s", (SITE,))
    conn.execute("DELETE FROM ref.site WHERE site_id = %s", (SITE,))


def advice(conn):
    """Conseils du site : (règle déclenchante, heure), sans les identifiants."""
    rows = conn.execute(
        "SELECT t.trigger_rule, r.target_time FROM app.recommendation r "
        "JOIN ref.recommendation_type t USING (recommendation_type_id) WHERE r.site_id = %s "
        "ORDER BY t.trigger_rule, r.target_time, t.message",
        (SITE,),
    ).fetchall()
    return rows


def refresh() -> int:
    with psycopg.connect(as_ml_role(DATABASE_URL), autocommit=True) as conn:
        return conn.execute("SELECT app.refresh_recommendations()").fetchone()[0]


@pytest.fixture
def seeded():
    """Un pic prévu dans deux heures et une alerte de pic soudain il y a une heure."""
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    peak_hour = hour + timedelta(hours=2)
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        cleanup(conn)
        conn.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) "
            "VALUES (%s, 'Site de test', 'office', 500)",
            (SITE,),
        )
        conn.execute(
            "INSERT INTO ml.prediction (target_time, site_id, model_version, predicted_kw, is_peak, predicted_at) "
            "VALUES (%s, %s, %s, 150, true, %s)",
            (peak_hour, SITE, VERSION, now - timedelta(minutes=30)),
        )
        conn.execute(
            "INSERT INTO core.alert (alert_id, time, site_id, severity, alert_type, origin) "
            "VALUES ('rec-test-1', %s, %s, 'high', 'spike', 'api')",
            (now - timedelta(hours=1), SITE),
        )
        yield peak_hour, hour - timedelta(hours=1)
        cleanup(conn)


def test_refresh_creates_advice_for_a_predicted_peak_and_an_alert(seeded):
    peak_hour, alert_hour = seeded

    assert refresh() == 2

    with psycopg.connect(DATABASE_URL) as conn:
        # Un bureau : un conseil de pic prévu, et le conseil générique d'un pic soudain
        assert advice(conn) == [("spike", alert_hour), ("threshold", peak_hour)]


def test_refresh_is_replayable(seeded):
    refresh()
    with psycopg.connect(DATABASE_URL) as conn:
        first = advice(conn)

    refresh()

    with psycopg.connect(DATABASE_URL) as conn:
        assert advice(conn) == first


def test_a_newer_prediction_cancels_the_peak_but_keeps_past_advice(seeded):
    peak_hour, alert_hour = seeded
    refresh()
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO ml.prediction (target_time, site_id, model_version, predicted_kw, is_peak) "
            "VALUES (%s, %s, %s, 100, false)",
            (peak_hour, SITE, VERSION + "-2"),
        )

    refresh()

    with psycopg.connect(DATABASE_URL) as conn:
        assert advice(conn) == [("spike", alert_hour)]


def test_ml_role_cannot_write_recommendations_directly(seeded):
    with (
        psycopg.connect(as_ml_role(DATABASE_URL)) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute(
            "INSERT INTO app.recommendation (recommendation_type_id, site_id, target_time) "
            "SELECT recommendation_type_id, %s, now() FROM ref.recommendation_type LIMIT 1",
            (SITE,),
        )


def test_python_wrapper_calls_the_function_with_the_ml_role(seeded):
    from enervision_ml import data

    assert data.refresh_recommendations(as_ml_role(DATABASE_URL)) == 2
