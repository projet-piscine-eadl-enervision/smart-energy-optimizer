"""Route /predictions : lecture de ml.prediction, avec une fausse session."""
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest


def row(hour: int, site_id="ALL", kw="12.5", peak=None, version="2"):
    return SimpleNamespace(
        target_time=datetime(2026, 10, 27, hour, tzinfo=UTC),
        site_id=site_id,
        predicted_kw=Decimal(kw),
        is_peak=peak,
        model_version=version,
    )


def test_predictions_total_by_default(client, db, auth_headers):
    db.rows = [row(10), row(11, kw="13.25")]

    response = client.get("/predictions", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {"timestamp": "2026-10-27T10:00:00Z", "site_id": "ALL", "predicted_kw": 12.5,
         "is_peak": None, "model_version": "2", "confidence": None},
        {"timestamp": "2026-10-27T11:00:00Z", "site_id": "ALL", "predicted_kw": 13.25,
         "is_peak": None, "model_version": "2", "confidence": None},
    ]
    sql, params = db.executed[0]
    assert "sum(predicted_kw)" in sql
    assert params == {"hours": 24}


def test_predictions_for_one_site(client, db, auth_headers):
    db.rows = [row(10, site_id="SITE001", peak=True)]

    response = client.get("/predictions?site_id=SITE001&hours=6", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()[0]["site_id"] == "SITE001"
    assert response.json()[0]["is_peak"] is True
    sql, params = db.executed[0]
    assert "site_id = :site_id" in sql
    assert params == {"hours": 6, "site_id": "SITE001"}


def test_predictions_empty_without_forecast(client, auth_headers):
    response = client.get("/predictions", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("hours", [0, 73, "abc"])
def test_predictions_invalid_hours(client, auth_headers, hours):
    assert client.get(f"/predictions?hours={hours}", headers=auth_headers).status_code == 422


def peak_row(hour: int, site_id="SITE001", kw="130", threshold="120", version="2"):
    return SimpleNamespace(
        target_time=datetime(2026, 10, 27, hour, tzinfo=UTC),
        site_id=site_id,
        predicted_kw=Decimal(kw),
        threshold_kw=None if threshold is None else Decimal(threshold),
        model_version=version,
    )


def test_peaks_with_threshold_and_excess(client, db, auth_headers):
    db.rows = [peak_row(10), peak_row(11, site_id="SITE002", kw="95.5", threshold="90")]

    response = client.get("/predictions/peaks", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {"timestamp": "2026-10-27T10:00:00Z", "site_id": "SITE001", "predicted_kw": 130.0,
         "threshold_kw": 120.0, "excess_kw": 10.0, "model_version": "2"},
        {"timestamp": "2026-10-27T11:00:00Z", "site_id": "SITE002", "predicted_kw": 95.5,
         "threshold_kw": 90.0, "excess_kw": 5.5, "model_version": "2"},
    ]
    sql, params = db.executed[0]
    assert "ml.peak_threshold" in sql
    assert params == {"hours": 24, "site_id": None}


def test_peaks_keep_a_peak_without_known_threshold(client, db, auth_headers):
    db.rows = [peak_row(10, threshold=None)]

    peak = client.get("/predictions/peaks?site_id=SITE001&hours=12", headers=auth_headers).json()[0]

    assert peak["threshold_kw"] is None
    assert peak["excess_kw"] is None
    assert db.executed[0][1] == {"hours": 12, "site_id": "SITE001"}


@pytest.mark.parametrize("hours", [0, 73, "abc"])
def test_peaks_invalid_hours(client, auth_headers, hours):
    assert client.get(f"/predictions/peaks?hours={hours}", headers=auth_headers).status_code == 422
