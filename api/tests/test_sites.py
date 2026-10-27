"""Routes /sites : liste, consommation par période et qualité, avec une fausse session."""
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace


def site_row(site_id="SITE001", consumption="42.5", quality="good"):
    return SimpleNamespace(
        site_id=site_id,
        site_name="Site 1",
        site_type="office",
        location="Nantes",
        capacity_kw=Decimal("500"),
        status="active",
        last_consumption_kw=None if consumption is None else Decimal(consumption),
        last_reading_age_minutes=None if consumption is None else Decimal("1.5"),
        last_quality=quality,
    )


def test_sites_are_listed_with_their_last_reading(client, db, auth_headers):
    db.rows = [site_row(), site_row("SITE002", consumption=None, quality=None)]

    response = client.get("/sites", headers=auth_headers)

    assert response.status_code == 200
    first, second = response.json()
    assert first["site_id"] == "SITE001"
    assert first["capacity_kw"] == 500.0
    assert first["last_consumption_kw"] == 42.5
    assert first["last_reading_age_minutes"] == 1.5
    assert first["last_quality"] == "good"
    assert second["last_consumption_kw"] is None
    assert second["last_quality"] is None


def point(energy="1200.5", max_kw="80"):
    return SimpleNamespace(
        ts=datetime(2026, 10, 26, tzinfo=UTC), energy_kwh=Decimal(energy), max_kw=Decimal(max_kw)
    )


def test_consumption_by_day_by_default(client, db, auth_headers):
    db.rows = [point()]

    response = client.get("/sites/SITE001/consumption", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {"timestamp": "2026-10-26T00:00:00Z", "energy_kwh": 1200.5, "max_kw": 80.0}
    ]
    sql, params = db.executed[1]  # la première requête vérifie que le site existe
    assert "analytics.energy_daily" in sql
    assert params == {"site_id": "SITE001", "days": 30, "unit": "day"}


def test_consumption_by_hour_reads_the_hourly_aggregate(client, db, auth_headers):
    db.rows = [point()]
    response = client.get("/sites/SITE001/consumption?period=hour&days=1", headers=auth_headers)

    assert response.status_code == 200
    sql, params = db.executed[1]
    assert "analytics.energy_hourly" in sql
    assert params == {"site_id": "SITE001", "days": 1}


def test_consumption_by_week_and_month_group_the_days(client, db, auth_headers):
    db.rows = [point()]
    client.get("/sites/SITE001/consumption?period=week", headers=auth_headers)
    client.get("/sites/SITE001/consumption?period=month", headers=auth_headers)

    assert db.executed[1][1] == {"site_id": "SITE001", "days": 90, "unit": "week"}
    assert db.executed[3][1] == {"site_id": "SITE001", "days": 365, "unit": "month"}


def test_consumption_rejects_an_unknown_period(client, auth_headers):
    assert client.get("/sites/SITE001/consumption?period=year", headers=auth_headers).status_code == 422


def test_unknown_site_is_a_404(client, db, auth_headers):
    db.rows = []

    for route in ("consumption", "quality"):
        # Aucune ligne : le site n'existe pas (first() renvoie None)
        response = client.get(f"/sites/SITE404/{route}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json() == {"detail": "Site inconnu"}


def test_quality_summarises_the_readings(client, db, auth_headers):
    db.rows = [
        SimpleNamespace(
            readings=1000, missing=50, good=900, partial=60, degraded=30, critical=10, outages=3
        )
    ]

    response = client.get("/sites/SITE001/quality?days=14", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "site_id": "SITE001",
        "days": 14,
        "readings": 1000,
        "missing_ratio": 0.05,
        "by_quality": {"good": 900, "partial": 60, "degraded": 30, "critical": 10},
        "sensor_outages": 3,
    }
    assert db.executed[1][1] == {"site_id": "SITE001", "days": 14}


def test_quality_without_readings_has_no_ratio(client, db, auth_headers):
    db.rows = [
        SimpleNamespace(readings=0, missing=0, good=0, partial=0, degraded=0, critical=0, outages=0)
    ]

    response = client.get("/sites/SITE001/quality", headers=auth_headers)

    assert response.json()["missing_ratio"] is None


def test_quality_days_are_bounded(client, auth_headers):
    assert client.get("/sites/SITE001/quality?days=31", headers=auth_headers).status_code == 422
