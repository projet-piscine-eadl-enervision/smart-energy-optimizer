"""Chargement de ref.site, sans base : fausse connexion et mock simulé."""
from decimal import Decimal

import httpx2
import pytest

from pipeline import db
from pipeline.jobs import load_ref
from tests.conftest import SITE_EXAMPLE
from tests.fakedb import FakeConnection

SITES = [SITE_EXAMPLE, {**SITE_EXAMPLE, "site_id": "SITE002", "site_type": "factory", "capacity_kw": 1000}]


def connection(*, known_types=(("office",), ("factory",)), raw_id=10):
    # Lectures dans l'ordre : etl.run (id), raw.api_response (id), types connus, puis le reste vide
    return FakeConnection(results=[[(1,)], [(raw_id,)], list(known_types)])


def wrote(conn, fragment):
    return any(fragment in sql for sql, _ in conn.calls)


@pytest.mark.anyio
async def test_loads_sites_and_tracks_the_run(mock_api):
    mock_api(lambda request: httpx2.Response(200, json=SITES))
    conn = connection()

    assert await load_ref.run(conn) == 2

    upsert = next(rows for sql, rows in conn.calls if "INSERT INTO ref.site" in sql)
    assert [row["site_id"] for row in upsert] == ["SITE001", "SITE002"]
    assert upsert[1]["capacity_kw"] == Decimal("1000.0")
    assert conn.calls[-2][0].startswith("UPDATE raw.api_response")
    assert conn.calls[-1][1] == ("success", 2, 0, None, 1)


@pytest.mark.anyio
async def test_unknown_site_type_fails_the_run_and_keeps_the_raw_response(mock_api):
    mock_api(lambda request: httpx2.Response(200, json=SITES))
    conn = connection(known_types=(("office",),))

    with pytest.raises(ValueError, match="factory"):
        await load_ref.run(conn)

    assert wrote(conn, "INSERT INTO raw.api_response")
    assert not wrote(conn, "INSERT INTO ref.site")
    assert conn.calls[-1][1][0] == "failed"


@pytest.mark.anyio
@pytest.mark.parametrize("response", [httpx2.Response(500, json={"detail": "boom"}), httpx2.Response(200, json=[])])
async def test_bad_answer_is_kept_raw_then_fails(mock_api, response):
    mock_api(lambda request: response)
    conn = connection()

    with pytest.raises((RuntimeError, ValueError)):
        await load_ref.run(conn)

    assert wrote(conn, "INSERT INTO raw.api_response")
    assert conn.calls[-1][1][0] == "failed"


@pytest.mark.anyio
async def test_network_error_fails_the_run(mock_api):
    def refuse(request):
        raise httpx2.ConnectError("unreachable")

    mock_api(refuse)
    conn = FakeConnection(results=[[(1,)]])

    with pytest.raises(httpx2.ConnectError):
        await load_ref.run(conn)

    assert conn.calls[-1][1][0] == "failed"


def test_main_loads_through_the_database_connection(monkeypatch, mock_api):
    mock_api(lambda request: httpx2.Response(200, json=SITES))
    conn = connection()
    monkeypatch.setattr(db, "connect", lambda: conn)

    load_ref.main([])

    assert conn.calls[-1][1] == ("success", 2, 0, None, 1)
