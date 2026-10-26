"""Collecteur des mesures courantes, sans base : fausse connexion et mock simulé."""
import asyncio
import itertools
from datetime import UTC, datetime

import httpx2
import psycopg
import pytest

from pipeline import db, heartbeat
from pipeline.jobs import poll_current
from pipeline.jobs.poll_current import Known, Summary, Tour
from tests.conftest import READING_PAYLOAD
from tests.fakedb import FakeConnection

SITES = ["SITE001", "SITE002"]
KNOWN = Known(SITES, {"outage", "spike"}, {"low", "critical"})
ALERT = {
    "alert_id": "ALR-SITE001-1", "timestamp": "2026-10-24T12:15:55.273602", "site_id": "SITE001",
    "severity": "critical", "type": "outage", "message": "Risque de surcharge", "value": 741.1, "threshold": 630.0,
}
SENSOR_OK = {"status": "ok", "failing_until": None}
STATUS_PAYLOAD = {
    "SITE001": {
        "site_name": "Bureau", "overall": "degraded",
        "sensors": {
            "consumption": {"status": "failing", "failing_until": "2026-10-24T12:00:45"},
            "electrical": SENSOR_OK, "temperature": SENSOR_OK, "humidity": SENSOR_OK, "network": SENSOR_OK,
        },
    }
}


def database(*, sites=SITES, latest=()):
    ids = itertools.count(1)

    def respond(sql, params):
        if sql.startswith("INSERT INTO raw.api_response"):
            return [(next(ids),)]
        if sql.startswith("INSERT INTO etl.run"):
            return [(99,)]
        if "FROM ref.site" in sql:
            return [(site,) for site in sites]
        if "FROM ref.alert_type" in sql:
            return [("outage",), ("spike",)]
        if "FROM ref.severity" in sql:
            return [("low",), ("critical",)]
        if "DISTINCT ON" in sql:
            return list(latest)
        return []

    return FakeConnection(responder=respond)


def mock_answers(*, alerts=(ALERT,), status=STATUS_PAYLOAD, failing_site=None):
    def handler(request):
        path = request.url.path
        if path.endswith("/sensors/status"):
            return httpx2.Response(200, json=status)
        if path.endswith("/alerts"):
            return httpx2.Response(200, json=list(alerts))
        site = path.split("/")[-2]
        if site == failing_site:
            return httpx2.Response(500, json={"detail": "boom"})
        return httpx2.Response(200, json={**READING_PAYLOAD, "site_id": site})

    return handler


def writes(conn, fragment):
    return [rows for sql, rows in conn.calls if fragment in sql]


@pytest.mark.anyio
async def test_tour_loads_readings_sensors_and_alerts(mock_api):
    mock_api(mock_answers())
    conn = database()

    result = await poll_current.tour(conn, KNOWN)

    assert (result.loaded, result.rejected, result.alerts, result.sensor_changes) == (2, 0, 1, 1)
    assert result.ok
    readings = writes(conn, "INSERT INTO core.energy_reading")[0]
    assert [row["site_id"] for row in readings] == SITES
    assert all(row["source"] == "current" and row["raw_id"] for row in readings)
    assert writes(conn, "INSERT INTO core.sensor_status")[0][0]["sensor"] == "consumption"
    assert writes(conn, "INSERT INTO core.alert")[0][0]["origin"] == "api"
    assert len(writes(conn, "INSERT INTO raw.api_response")) == 4
    assert sorted(writes(conn, "SET processed_at")[0][0]) == [1, 2, 3, 4]


@pytest.mark.anyio
async def test_alert_with_unknown_type_is_rejected_not_fatal(mock_api):
    mock_api(mock_answers(alerts=[{**ALERT, "type": "spaceport"}]))
    conn = database()

    result = await poll_current.tour(conn, KNOWN)

    assert result.alerts == 0 and result.rejected == 1
    assert result.loaded == 2
    assert not writes(conn, "INSERT INTO core.alert")


@pytest.mark.anyio
async def test_a_failing_site_does_not_stop_the_others_and_its_answer_is_kept(mock_api):
    mock_api(mock_answers(failing_site="SITE002"))
    conn = database()

    result = await poll_current.tour(conn, KNOWN)

    assert result.loaded == 1 and result.rejected == 1
    assert "SITE002" in result.errors[0] and "HTTP 500" in result.errors[0]
    assert len(writes(conn, "INSERT INTO raw.api_response")) == 4
    assert len(writes(conn, "SET processed_at")[0][0]) == 3  # l'échec reste « à traiter »


@pytest.mark.anyio
async def test_unreachable_mock_loads_nothing(mock_api):
    def refuse(request):
        raise httpx2.ConnectError("unreachable")

    mock_api(refuse)
    conn = database()

    result = await poll_current.tour(conn, KNOWN)

    assert not result.ok and result.loaded == 0 and result.rejected == 4
    assert not writes(conn, "INSERT INTO core.energy_reading")


@pytest.mark.anyio
async def test_unexpected_payload_is_rejected(mock_api):
    mock_api(lambda request: httpx2.Response(200, json={"surprise": True}))
    conn = database()

    result = await poll_current.tour(conn, KNOWN)

    assert result.loaded == 0 and result.rejected == 4


@pytest.mark.anyio
async def test_ensure_sites_loads_the_reference_when_empty(monkeypatch):
    state = {"loaded": False}

    def respond(sql, params):
        if "FROM ref.site" in sql:
            return [("SITE001",)] if state["loaded"] else []
        return [("outage",)]

    async def load(conn):
        state["loaded"] = True

    monkeypatch.setattr(poll_current.load_ref, "run", load)

    known = await poll_current.ensure_sites(FakeConnection(responder=respond))

    assert known.sites == ["SITE001"] and known.alert_types == {"outage"}


def test_account_writes_a_summary_every_ten_tours_and_one_run_per_failure_series():
    conn = database()
    summary = Summary()
    good, bad = Tour(loaded=7), Tour(errors=["mock down"], rejected=9)

    for _ in range(9):
        poll_current.account(conn, summary, good)
    assert not writes(conn, "INSERT INTO etl.run")
    poll_current.account(conn, summary, good)
    assert len(writes(conn, "INSERT INTO etl.run")) == 1
    assert summary.tours == 0

    for _ in range(3):
        poll_current.account(conn, summary, bad)
    runs = writes(conn, "INSERT INTO etl.run")
    assert len(runs) == 2  # une seule ligne pour la série d'échecs
    finished = writes(conn, "UPDATE etl.run")
    assert [params[0] for params in finished] == ["success", "failed"]
    assert finished[1][3] == "mock down"


@pytest.mark.anyio
async def test_run_forever_once_beats_when_the_tour_succeeds(mock_api, monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_FILE", str(tmp_path / "beat"))
    mock_api(mock_answers())
    conn = database()

    await poll_current.run_forever(lambda: conn, 60, asyncio.Event(), once=True)

    assert heartbeat.age() is not None and heartbeat.age() < 5
    assert conn.closed


@pytest.mark.anyio
async def test_run_forever_survives_a_database_outage_and_keeps_no_heartbeat(mock_api, monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_FILE", str(tmp_path / "beat"))
    mock_api(mock_answers())
    stop, attempts = asyncio.Event(), []

    def connect():
        attempts.append(1)
        if len(attempts) >= 2:
            stop.set()
        raise psycopg.OperationalError("database down")

    await poll_current.run_forever(connect, 0.01, stop)

    assert len(attempts) == 2
    assert heartbeat.age() is None


@pytest.mark.anyio
async def test_stop_signal_interrupts_the_wait_between_tours(mock_api, monkeypatch, tmp_path):
    monkeypatch.setenv("HEARTBEAT_FILE", str(tmp_path / "beat"))
    mock_api(mock_answers())
    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(0.2, stop.set)

    await asyncio.wait_for(poll_current.run_forever(lambda: database(), 3600, stop), timeout=5)


def test_main_runs_one_tour_and_rejects_a_bad_interval(monkeypatch, mock_api, tmp_path):
    monkeypatch.setenv("HEARTBEAT_FILE", str(tmp_path / "beat"))
    mock_api(mock_answers())
    conn = database()
    monkeypatch.setattr(db, "connect", lambda: conn)

    poll_current.main(["--once", "--interval", "30"])

    assert writes(conn, "INSERT INTO core.energy_reading")
    with pytest.raises(SystemExit):
        poll_current.main(["--interval", "0"])


def test_write_run_records_the_period():
    conn = database()
    summary = Summary(loaded=5, rejected=1, period_start=datetime(2026, 10, 24, tzinfo=UTC))

    poll_current.write_run(conn, summary, datetime(2026, 10, 24, 0, 10, tzinfo=UTC))

    assert writes(conn, "INSERT INTO etl.run")[0] == ("poll_current", summary.period_start, datetime(2026, 10, 24, 0, 10, tzinfo=UTC))
