"""Chargement de ref.site sur une vraie base migrée. Ignoré sans DATABASE_URL.

Local : docker compose up -d db && docker compose run --rm migrate, puis
DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision python -m pytest tests/test_load_ref_db.py
Tout est annulé à la fin de chaque test (transaction abandonnée).
"""
import os

import httpx2
import pytest

from pipeline import db
from pipeline.jobs import load_ref
from tests.conftest import SITE_EXAMPLE

# Identifiant propre au test : la base peut déjà contenir les vrais sites
SITE = {**SITE_EXAMPLE, "site_id": "SITE999"}

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL absent")


@pytest.fixture
def conn():
    with db.connect() as connection, connection.transaction(force_rollback=True):
        yield connection


def rows_of_test_site(conn):
    return conn.execute("SELECT site_name, capacity_kw FROM ref.site WHERE site_id = %s", (SITE["site_id"],)).fetchall()


@pytest.mark.anyio
async def test_loads_then_updates_without_duplicates(conn, mock_api):
    answers = iter([[SITE], [{**SITE, "capacity_kw": 300.5}]])
    mock_api(lambda request: httpx2.Response(200, json=next(answers)))

    assert await load_ref.run(conn) == 1
    assert await load_ref.run(conn) == 1

    rows = rows_of_test_site(conn)
    assert len(rows) == 1
    assert float(rows[0][1]) == 300.5
    runs = conn.execute(
        "SELECT status, rows_loaded FROM etl.run WHERE run_type = 'ref_load' ORDER BY run_id"
    ).fetchall()
    assert runs[-2:] == [("success", 1), ("success", 1)]
    assert conn.execute("SELECT count(*) FROM raw.api_response WHERE processed_at IS NOT NULL").fetchone()[0] >= 2


@pytest.mark.anyio
async def test_unknown_type_is_refused_before_any_write(conn, mock_api):
    mock_api(lambda request: httpx2.Response(200, json=[{**SITE, "site_type": "spaceport"}]))

    with pytest.raises(ValueError, match="spaceport"):
        await load_ref.run(conn)

    assert rows_of_test_site(conn) == []
    assert conn.execute("SELECT status FROM etl.run ORDER BY run_id DESC LIMIT 1").fetchone()[0] == "failed"
