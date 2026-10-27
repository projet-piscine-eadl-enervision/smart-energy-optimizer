"""Chargement de l'historique nettoyé, sans base : fausse connexion et petit fichier parquet."""
from decimal import Decimal

import pandas as pd
import pytest

from pipeline.jobs import load_history
from pipeline.rows import history_rows
from tests.fakedb import FakeConnection

NA = pd.NA


def history(rows=None):
    """Quatre heures de SITE001 : une anomalie, une valeur manquante, une interpolée."""
    base = {
        "timestamp": pd.date_range("2023-01-01", periods=4, freq="h", tz="UTC"),
        "site_id": "SITE001",
        "consumption_kwh_clean": [100.5, float("nan"), 90.0, 95.25],
        "consumption_kwh_source": ["measured", "missing", "interpolated", "recovered_from_euros"],
        "temperature_celsius_clean": [10.0, 11.0, float("nan"), 12.0],
        "humidity_percent_clean": [50.0, 51.0, 52.0, 53.0],
        "solar_irradiance_wm2_clean": [0.0, 0.0, 0.0, 5.0],
        "anomaly_type": pd.array([NA, NA, "spike", NA], dtype="string"),
        "anomaly_severity": pd.array([NA, NA, "high", NA], dtype="string"),
    }
    return pd.DataFrame({**base, **(rows or {})})


def save(tmp_path, frame):
    path = tmp_path / "history.parquet"
    frame.to_parquet(path)
    return path


def connection(*, sites=("SITE001",), types=("spike", "outage"), severities=("medium", "high")):
    def answer(sql, params):
        if sql.startswith("INSERT INTO etl.run"):
            return [(1,)]
        if sql == load_history.SITE_IDS:
            return [(s,) for s in sites]
        if sql == load_history.ALERT_TYPES:
            return [(t,) for t in types]
        if sql == load_history.SEVERITIES:
            return [(s,) for s in severities]
        return []

    return FakeConnection(responder=answer)


def written(conn):
    return next(rows for sql, rows in conn.calls if "INSERT INTO ml.history_labeled" in sql)


def test_missing_values_become_null_not_nan():
    rows = history_rows(history())

    assert rows[0]["consumption_kw"] == Decimal("100.5")
    assert rows[1]["consumption_kw"] is None  # valeur manquante : NULL, jamais NaN
    assert rows[2]["temperature_celsius"] is None
    assert rows[2]["anomaly_type"] == "spike" and rows[2]["anomaly_severity"] == "high"
    assert rows[0]["anomaly_type"] is None and rows[0]["anomaly_severity"] is None
    assert rows[0]["time"].tzinfo is not None and rows[0]["time"].isoformat() == "2023-01-01T00:00:00+00:00"
    assert all(Decimal("NaN") != value for row in rows for value in row.values() if isinstance(value, Decimal))


def test_loads_the_file_and_tracks_the_run(tmp_path):
    conn = connection()

    assert load_history.run(conn, save(tmp_path, history())) == (4, 0)

    assert [row["site_id"] for row in written(conn)] == ["SITE001"] * 4
    assert conn.calls[-1][1] == ("success", 4, 0, None, 1)
    assert not any("raw.api_response" in sql for sql, _ in conn.calls), "la source est un fichier, pas le mock"


def test_unknown_site_fails_the_run_and_asks_for_load_ref(tmp_path):
    conn = connection(sites=("SITE002",))

    with pytest.raises(RuntimeError, match=r"SITE001.*load-ref"):
        load_history.run(conn, save(tmp_path, history()))

    assert conn.calls[-1][1][0] == "failed"
    assert not any("INSERT INTO ml.history_labeled" in sql for sql, _ in conn.calls)


def test_unknown_anomaly_or_source_is_rejected_and_counted(tmp_path):
    frame = history({
        "consumption_kwh_source": ["measured", "bidon", "interpolated", "measured"],
        "anomaly_type": pd.array([NA, NA, "inconnu", NA], dtype="string"),
    })
    conn = connection()

    assert load_history.run(conn, save(tmp_path, frame)) == (2, 2)

    assert [row["time"].hour for row in written(conn)] == [0, 3]
    assert conn.calls[-1][1] == ("success", 2, 2, None, 1)


def test_an_anomaly_without_severity_is_rejected(tmp_path):
    frame = history({"anomaly_severity": pd.array([NA, NA, NA, NA], dtype="string")})

    assert load_history.run(connection(), save(tmp_path, frame)) == (3, 1)


def test_duplicate_keys_are_refused(tmp_path):
    frame = pd.concat([history(), history().iloc[:1]], ignore_index=True)
    conn = connection()

    with pytest.raises(ValueError, match="1 duplicated"):
        load_history.run(conn, save(tmp_path, frame))

    assert conn.calls[-1][1][0] == "failed"


def test_a_file_without_the_expected_columns_is_refused(tmp_path):
    with pytest.raises(ValueError, match="anomaly_severity"):
        load_history.read_history(save(tmp_path, history().drop(columns=["anomaly_severity"])))


def test_upsert_only_touches_rows_whose_values_changed():
    assert "ON CONFLICT (site_id, time) DO UPDATE" in load_history.UPSERT
    assert "IS DISTINCT FROM" in load_history.UPSERT
