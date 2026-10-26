"""Rattrapage de l'historique, sans base : fausse connexion et mock simulé qui répond par grille."""
import logging
from datetime import UTC, datetime, timedelta

import httpx2
import pytest

from pipeline import db
from pipeline.jobs import backfill
from tests.conftest import READING_PAYLOAD
from tests.fakedb import FakeConnection

START = datetime(2024, 3, 1, tzinfo=UTC)


def hours(count: int) -> timedelta:
    return timedelta(hours=count)


def grid(request):
    """Comme le mock : `limit` points répartis sur la fenêtre, début inclus, fin exclue."""
    params = request.url.params
    start = datetime.fromisoformat(params["start_time"])
    items = [
        {
            **READING_PAYLOAD,
            "site_id": params["site_id"],
            "timestamp": (start + hours(k)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        for k in range(int(params["limit"]))
    ]
    return httpx2.Response(200, json=items)


def database(sites=("SITE001", "SITE002")):
    ids = iter(range(1, 10_000))

    def respond(sql, params):
        if sql.startswith(("INSERT INTO raw.api_response", "INSERT INTO etl.run")):
            return [(next(ids),)]
        if "FROM ref.site" in sql:
            return [(site,) for site in sites]
        return []

    return FakeConnection(responder=respond)


def writes(conn, fragment):
    return [rows for sql, rows in conn.calls if fragment in sql]


def test_windows_are_cut_every_1000_hours_and_cover_the_period_exactly():
    assert list(backfill.windows(START, START + hours(2500))) == [
        (START, 1000), (START + hours(1000), 1000), (START + hours(2000), 500),
    ]
    assert list(backfill.windows(START, START + hours(1))) == [(START, 1)]
    assert list(backfill.windows(START, START)) == []


def test_moments_are_rounded_down_to_the_hour_in_utc():
    assert backfill.parse_moment("2024-03-01T10:45:30") == datetime(2024, 3, 1, 10, tzinfo=UTC)
    assert backfill.parse_moment("2024-03-01T12:10:00+02:00") == datetime(2024, 3, 1, 10, tzinfo=UTC)
    assert backfill.parse_moment("2024-03-01") == START


@pytest.mark.anyio
async def test_a_site_is_loaded_window_by_window_with_one_point_per_hour(mock_api):
    requests = mock_api(grid)
    conn = database()

    loaded, errors = await backfill.backfill_site(conn, "SITE001", START, START + hours(2500))

    assert (loaded, errors) == (2500, [])
    assert [int(r.url.params["limit"]) for r in requests] == [1000, 1000, 500]
    assert requests[1].url.params["start_time"] == (START + hours(1000)).isoformat()
    rows = [row for batch in writes(conn, "INSERT INTO core.energy_reading") for row in batch]
    assert len(rows) == 2500 and {row["source"] for row in rows} == {"readings"}
    assert all(row["time"] == row["mock_time"] and row["time"].minute == 0 for row in rows)
    assert writes(conn, "UPDATE etl.run")[0][:3] == ("success", 2500, 0)


@pytest.mark.anyio
async def test_a_second_pass_asks_for_the_same_instants(mock_api):
    requests = mock_api(grid)
    conn = database()

    await backfill.backfill_site(conn, "SITE001", START, START + hours(1500))
    first = [dict(r.url.params) for r in requests]
    await backfill.backfill_site(conn, "SITE001", START, START + hours(1500))

    assert [dict(r.url.params) for r in requests[len(first):]] == first


@pytest.mark.anyio
async def test_a_failed_window_is_recorded_and_the_next_ones_still_load(mock_api):
    def flaky(request):
        if request.url.params["start_time"] == START.isoformat():
            return httpx2.Response(500, json={"detail": "boom"})
        return grid(request)

    mock_api(flaky)
    conn = database()

    loaded, errors = await backfill.backfill_site(conn, "SITE001", START, START + hours(1500))

    assert loaded == 500 and len(errors) == 1 and "HTTP 500" in errors[0]
    finished = writes(conn, "UPDATE etl.run")[0]
    assert finished[0] == "failed" and finished[2] == 1000


@pytest.mark.anyio
async def test_network_error_and_wrong_payload_are_errors_not_crashes(mock_api):
    calls = iter([httpx2.ConnectError("unreachable"), httpx2.Response(200, json={"surprise": True})])

    def answer(request):
        reply = next(calls)
        if isinstance(reply, Exception):
            raise reply
        return reply

    mock_api(answer)

    loaded, errors = await backfill.backfill_site(database(), "SITE001", START, START + hours(2000))

    assert loaded == 0 and len(errors) == 2


@pytest.mark.anyio
async def test_short_answer_is_reported(mock_api, caplog):
    mock_api(lambda request: httpx2.Response(200, json=[]))

    with caplog.at_level(logging.WARNING):
        await backfill.backfill_site(database(), "SITE001", START, START + hours(3))

    assert "0 points received, 3 expected" in caplog.text


@pytest.mark.anyio
async def test_run_refreshes_the_aggregates_after_loading_every_site(mock_api):
    mock_api(grid)
    conn = database()

    total = await backfill.run(conn, START, START + hours(24))

    assert total == 48
    statements = [sql for sql, _ in conn.calls]
    assert "CALL refresh_continuous_aggregate('analytics.energy_hourly'" in statements[-2]
    assert statements[-1] == "SELECT analytics.refresh_site_baseline()"
    assert conn.calls[-2][1] == (START, START + hours(24))


@pytest.mark.anyio
async def test_run_refreshes_then_fails_when_a_window_failed(mock_api):
    mock_api(lambda request: httpx2.Response(500, json={}))
    conn = database()

    with pytest.raises(RuntimeError, match="2 windows failed"):
        await backfill.run(conn, START, START + hours(24))

    assert conn.calls[-1][0] == "SELECT analytics.refresh_site_baseline()"


@pytest.mark.anyio
async def test_run_can_target_one_site_and_refuses_an_unknown_one(mock_api):
    requests = mock_api(grid)
    conn = database()

    await backfill.run(conn, START, START + hours(2), only_site="SITE002")
    assert {r.url.params["site_id"] for r in requests} == {"SITE002"}

    with pytest.raises(ValueError, match="SITE404"):
        await backfill.run(conn, START, START + hours(2), only_site="SITE404")


def test_main_loads_the_requested_period(monkeypatch, mock_api):
    requests = mock_api(grid)
    conn = database(sites=("SITE001",))
    monkeypatch.setattr(db, "connect", lambda: conn)

    backfill.main(["--start", "2024-03-01", "--end", "2024-03-01T03:30"])

    assert [int(r.url.params["limit"]) for r in requests] == [3]
    assert requests[0].url.params["end_time"] == "2024-03-01T03:00:00+00:00"


def test_main_refuses_an_empty_period():
    with pytest.raises(SystemExit):
        backfill.main(["--start", "2024-03-02", "--end", "2024-03-01"])
