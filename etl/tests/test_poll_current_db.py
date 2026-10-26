"""Collecteur sur une vraie base migrée. Ignoré sans DATABASE_URL.

Local : docker compose up -d db && docker compose run --rm migrate, puis
DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision python -m pytest tests/test_poll_current_db.py
Tout est annulé à la fin de chaque test (transaction abandonnée).
"""
import copy
import os
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from pipeline import db
from pipeline.jobs import poll_current
from tests.conftest import READING_PAYLOAD
from tests.test_poll_current import ALERT, STATUS_PAYLOAD

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL absent")


@pytest.fixture
def conn():
    with db.connect() as connection, connection.transaction(force_rollback=True):
        connection.execute(
            "INSERT INTO ref.site (site_id, site_name, site_type, location, capacity_kw, status)"
            " VALUES ('SITE999', 'test', 'office', 'test', 100, 'active')"
        )
        yield connection


def handler(alert):
    def answer(request):
        path = request.url.path
        if path.endswith("/sensors/status"):
            status = copy.deepcopy(STATUS_PAYLOAD["SITE001"])
            status["sensors"]["consumption"]["failing_until"] = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
            return httpx2.Response(200, json={"SITE999": status})
        if path.endswith("/alerts"):
            return httpx2.Response(200, json=[alert])
        return httpx2.Response(200, json={**READING_PAYLOAD, "site_id": "SITE999"})

    return answer


def count(conn, table, where="site_id = 'SITE999'"):
    return conn.execute(f"SELECT count(*) FROM {table} WHERE {where}").fetchone()[0]


@pytest.mark.anyio
async def test_tours_fill_the_tables_without_duplicates(conn, mock_api):
    mock_api(handler({**ALERT, "site_id": "SITE999", "alert_id": "ALR-TEST-1"}))
    known = poll_current.Known(["SITE999"], {"outage"}, {"critical"})

    first = await poll_current.tour(conn, known)
    second = await poll_current.tour(conn, known)

    assert first.loaded == second.loaded == 1
    assert count(conn, "core.energy_reading") == 2
    row = conn.execute("SELECT source, raw_id IS NOT NULL, mock_time <> time FROM core.energy_reading WHERE site_id = 'SITE999' LIMIT 1").fetchone()
    assert row == ("current", True, True)
    # La même panne vue à deux tours consécutifs reste un seul épisode, le mock annonce la même fin
    assert count(conn, "core.sensor_status") == 1
    assert count(conn, "core.alert", "alert_id = 'ALR-TEST-1'") == 1
    assert count(conn, "raw.api_response", "processed_at IS NULL AND endpoint LIKE '%SITE999%'") == 0


@pytest.mark.anyio
async def test_unknown_alert_type_does_not_cancel_the_tour(conn, mock_api):
    mock_api(handler({**ALERT, "site_id": "SITE999", "alert_id": "ALR-TEST-2", "type": "spaceport"}))
    known = poll_current.Known(["SITE999"], {"outage"}, {"critical"})

    result = await poll_current.tour(conn, known)

    assert result.loaded == 1 and result.rejected == 1
    assert count(conn, "core.energy_reading") == 1
    assert count(conn, "core.alert", "alert_id = 'ALR-TEST-2'") == 0


@pytest.mark.anyio
async def test_ensure_sites_reads_the_reference_tables(conn):
    known = await poll_current.ensure_sites(conn)

    assert "SITE999" in known.sites
    assert {"outage", "spike"} <= known.alert_types and {"low", "critical"} <= known.severities
