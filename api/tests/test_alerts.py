"""Route /alerts : lecture de core.alert, avec une fausse session."""
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace


def row(alert_id="ALR-SITE001-1", status="active", value="130.5", threshold=None):
    return SimpleNamespace(
        alert_id=alert_id,
        ts=datetime(2026, 10, 27, 10, 0, tzinfo=UTC),
        received_at=datetime(2026, 10, 27, 10, 5, tzinfo=UTC),
        site_id="SITE001",
        site_name="Site 1",
        severity="high",
        alert_type="threshold",
        alert_label="Dépassement du seuil",
        message="Seuil dépassé",
        value=Decimal(value),
        threshold=threshold,
        origin="api",
        status=status,
    )


def test_alerts_returns_active_alerts_by_default(client, db, auth_headers):
    db.rows = [row()]

    response = client.get("/alerts", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {
            "alert_id": "ALR-SITE001-1",
            "timestamp": "2026-10-27T10:00:00Z",
            "received_at": "2026-10-27T10:05:00Z",
            "site_id": "SITE001",
            "site_name": "Site 1",
            "severity": "high",
            "alert_type": "threshold",
            "alert_label": "Dépassement du seuil",
            "message": "Seuil dépassé",
            "value": 130.5,
            "threshold": None,
            "origin": "api",
            "status": "active",
        }
    ]
    _, params = db.executed[0]
    assert params["status"] == "active"
    assert params["site_id"] is None
    assert params["since"] is None
    assert params["limit"] == 50


def test_alerts_pass_the_filters_to_the_query(client, db, auth_headers):
    response = client.get(
        "/alerts?site_id=SITE003&status=all&since=2026-10-27T10:00:00Z&limit=5", headers=auth_headers
    )

    assert response.status_code == 200
    _, params = db.executed[0]
    assert params["site_id"] == "SITE003"
    assert params["status"] == "all"
    assert params["since"] == datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
    assert params["limit"] == 5


def test_alerts_status_uses_freshness_and_resolution(client, db, auth_headers):
    client.get("/alerts", headers=auth_headers)

    sql, params = db.executed[0]
    assert "resolved_at IS NULL" in sql
    assert "coalesce(a.last_seen_at, a.time)" in sql
    assert params["active_minutes"] == 15


def test_alerts_reject_an_unknown_status(client, auth_headers):
    assert client.get("/alerts?status=closed", headers=auth_headers).status_code == 422


def test_alerts_limit_is_bounded(client, auth_headers):
    assert client.get("/alerts?limit=0", headers=auth_headers).status_code == 422
    assert client.get("/alerts?limit=201", headers=auth_headers).status_code == 422
