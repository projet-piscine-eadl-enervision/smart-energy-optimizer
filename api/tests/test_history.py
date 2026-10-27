"""Route /history : lecture de analytics.energy_hourly, avec une fausse session."""
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace


def row(hour: int, kw="12.5"):
    return SimpleNamespace(ts=datetime(2026, 10, 27, hour, tzinfo=UTC), consumption_kw=Decimal(kw))


def test_history_total_by_default(client, db, auth_headers):
    db.rows = [row(8), row(9, kw="13.25")]

    response = client.get("/history", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {"timestamp": "2026-10-27T08:00:00Z", "consumption_kw": 12.5},
        {"timestamp": "2026-10-27T09:00:00Z", "consumption_kw": 13.25},
    ]
    sql, params = db.executed[0]
    assert "sum(avg_consumption_kw)" in sql
    assert params == {"days": 7}


def test_history_for_one_site(client, db, auth_headers):
    db.rows = [row(8)]

    response = client.get("/history?days=2&site_id=SITE001", headers=auth_headers)

    assert response.status_code == 200
    sql, params = db.executed[0]
    assert "site_id = :site_id" in sql
    assert params == {"days": 2, "site_id": "SITE001"}


def test_history_empty_without_data(client, auth_headers):
    response = client.get("/history", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []
