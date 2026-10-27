"""Métriques de l'ETL : lues dans etl.run et core.energy_reading (base simulée)."""
import psycopg
from prometheus_client import generate_latest

import main
from metrics import LAST_RUNS, LATEST_READING, build_registry
from tests.fakedb import FakeConnection


def scrape(connect) -> str:
    return generate_latest(build_registry(connect)).decode()


def test_metrics_from_database():
    def responder(sql, params):
        if sql == LAST_RUNS:
            return [("poll_current", "success", 1793000000.0, 420, 3), ("ref_load", "failed", 1792000000.0, 0, 0)]
        if sql == LATEST_READING:
            return [(1793000060.0,)]
        return []

    conn = FakeConnection(responder=responder)
    text = scrape(lambda: conn)
    assert 'etl_last_run_timestamp_seconds{run_type="poll_current",status="success"} 1.793e+09' in text
    assert 'etl_last_run_timestamp_seconds{run_type="ref_load",status="failed"}' in text
    assert 'etl_last_run_rows_loaded{run_type="poll_current"} 420.0' in text
    assert 'etl_last_run_rows_rejected{run_type="poll_current"} 3.0' in text
    assert "etl_latest_reading_timestamp_seconds 1.79300006e+09" in text
    assert "etl_metrics_up 1.0" in text
    assert conn.closed


def test_empty_database():
    text = scrape(lambda: FakeConnection(responder=lambda sql, params: [(None,)] if sql == LATEST_READING else []))
    assert "etl_metrics_up 1.0" in text
    # Aucune mesure en base : la métrique est déclarée (HELP, TYPE) mais sans valeur
    assert not any(line.startswith("etl_latest_reading_timestamp_seconds") for line in text.splitlines())


def test_database_unreachable():
    def refuse():
        raise psycopg.OperationalError("connection refused")

    text = scrape(refuse)
    assert "etl_metrics_up 0.0" in text


def test_metrics_route(client, monkeypatch):
    monkeypatch.setattr(main, "registry", build_registry(lambda: FakeConnection()))
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "etl_metrics_up" in response.text
