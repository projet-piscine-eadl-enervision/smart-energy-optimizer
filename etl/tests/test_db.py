"""Connexion à la base et suivi des exécutions (etl.run), sans base."""
import pytest

from pipeline import db
from pipeline.runs import finish_run, start_run
from tests.fakedb import FakeConnection


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        db.database_url()


def test_connect_uses_the_url_in_autocommit(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/d")
    received = {}
    monkeypatch.setattr(db.psycopg, "connect", lambda url, **kwargs: received.update(url=url, **kwargs) or "conn")

    assert db.connect() == "conn"
    assert received == {"url": "postgresql://u:p@h/d", "autocommit": True}


def test_start_run_returns_the_id_of_the_new_row():
    conn = FakeConnection(results=[[(42,)]])

    assert start_run(conn, "ref_load") == 42
    sql, params = conn.calls[0]
    assert sql.startswith("INSERT INTO etl.run")
    assert params == ("ref_load", None, None)
    assert conn.transactions == 1


def test_finish_run_success_and_failure():
    conn = FakeConnection()
    finish_run(conn, 7, rows_loaded=5)
    finish_run(conn, 8, error="boom")

    assert conn.calls[0][1] == ("success", 5, 0, None, 7)
    assert conn.calls[1][1] == ("failed", 0, 0, "boom", 8)
