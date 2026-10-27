"""Route /recommendations : lecture de app.recommendation, avec une fausse session."""
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest


def row(rec_id, hour, rule="threshold", label="Dépassement du seuil", saving="10"):
    return SimpleNamespace(
        recommendation_id=rec_id,
        site_id="SITE001",
        site_name="Bureau Paris",
        target_time=datetime(2026, 10, 27, hour, tzinfo=UTC),
        alert_type=rule,
        alert_label=label,
        message="Décaler les usages non critiques",
        saving_kw=None if saving is None else Decimal(saving),
    )


def test_recommendations_with_and_without_saving(client, db, auth_headers):
    db.rows = [row(1, 14), row(2, 9, rule="spike", label="Pic de consommation", saving=None)]

    response = client.get("/recommendations", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == [
        {"id": 1, "title": "Dépassement du seuil : Bureau Paris", "message": "Décaler les usages non critiques",
         "estimated_saving_kw": 10.0, "site_id": "SITE001", "target_time": "2026-10-27T14:00:00Z",
         "alert_type": "threshold"},
        {"id": 2, "title": "Pic de consommation : Bureau Paris", "message": "Décaler les usages non critiques",
         "estimated_saving_kw": None, "site_id": "SITE001", "target_time": "2026-10-27T09:00:00Z",
         "alert_type": "spike"},
    ]
    assert db.executed[0][1] == {"hours": 24, "site_id": None, "limit": 50}


def test_recommendations_for_one_site(client, db, auth_headers):
    response = client.get("/recommendations?site_id=SITE001&hours=6&limit=5", headers=auth_headers)

    assert response.status_code == 200
    assert db.executed[0][1] == {"hours": 6, "site_id": "SITE001", "limit": 5}


@pytest.mark.parametrize("query", ["hours=0", "hours=73", "limit=0", "limit=201", "hours=abc"])
def test_recommendations_invalid_parameters(client, auth_headers, query):
    assert client.get(f"/recommendations?{query}", headers=auth_headers).status_code == 422
