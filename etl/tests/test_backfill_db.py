"""Rattrapage sur une vraie base migrée. Ignoré sans DATABASE_URL.

Le rafraîchissement d'un agrégat ne peut pas se faire dans une transaction annulée : ces tests écrivent
pour de vrai, sur un site de test (SITE998) et l'an 2001, puis effacent tout à la fin.
Local : docker compose up -d db && docker compose run --rm migrate, puis
DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision python -m pytest tests/test_backfill_db.py
"""
import os
from datetime import UTC, datetime, timedelta

import pytest

from pipeline import db
from pipeline.jobs import backfill
from tests.test_backfill import grid

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL absent")

START = datetime(2001, 1, 1, tzinfo=UTC)
END = START + timedelta(hours=48)


def count(conn, table, where="site_id = 'SITE998'"):
    return conn.execute(f"SELECT count(*) FROM {table} WHERE {where}").fetchone()[0]


@pytest.fixture
def conn():
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, location, capacity_kw, status)"
            " VALUES ('SITE998', 'test', 'office', 'test', 100, 'active') ON CONFLICT DO NOTHING"
        )
        yield connection
        connection.execute("DELETE FROM core.energy_reading WHERE site_id = 'SITE998'")
        connection.execute("DELETE FROM raw.api_response WHERE params->>'site_id' = 'SITE998'")
        connection.execute("DELETE FROM etl.run WHERE run_type = 'backfill' AND period_start = %s", (START,))
        backfill.refresh(connection, START, END)
        connection.execute("DELETE FROM ref.site WHERE site_id = 'SITE998'")


@pytest.mark.anyio
async def test_backfill_is_idempotent_and_feeds_the_hourly_aggregate(conn, mock_api):
    mock_api(grid)

    assert await backfill.run(conn, START, END, only_site="SITE998") == 48
    assert count(conn, "core.energy_reading") == 48
    assert count(conn, "analytics.energy_hourly") == 48

    # Même période, puis fin plus courte : rien de nouveau, rien de dupliqué
    assert await backfill.run(conn, START, END, only_site="SITE998") == 0
    assert await backfill.run(conn, START, END - timedelta(hours=24), only_site="SITE998") == 0
    assert count(conn, "core.energy_reading") == 48

    statuses = conn.execute(
        "SELECT status, rows_loaded FROM etl.run WHERE run_type = 'backfill' AND period_start = %s ORDER BY run_id",
        (START,),
    ).fetchall()
    assert statuses == [("success", 48), ("success", 0), ("success", 0)]
    assert count(conn, "raw.api_response", "params->>'site_id' = 'SITE998' AND processed_at IS NULL") == 0
