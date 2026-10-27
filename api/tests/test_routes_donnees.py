"""Routes de données protégées : prédictions, historique, recommandations."""
import asyncio

import pytest
from fastapi import HTTPException

from app.api.deps import require_role
from app.models.user import Role, User

ROUTES_PROTEGEES = [
    "/predictions",
    "/predictions/peaks",
    "/history",
    "/recommendations",
    "/alerts",
    "/sites",
]


@pytest.mark.parametrize("route", ROUTES_PROTEGEES)
def test_route_refusee_sans_jeton(client, route):
    assert client.get(route).status_code == 401


@pytest.mark.parametrize("route", ROUTES_PROTEGEES)
def test_route_accessible_avec_jeton(client, auth_headers, route):
    response = client.get(route, headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.parametrize("days", [0, 91, "abc"])
def test_history_parametre_days_invalide(client, auth_headers, days):
    response = client.get(f"/history?days={days}", headers=auth_headers)
    assert response.status_code == 422


def test_require_role_refuse_un_role_insuffisant():
    checker = require_role(Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(checker(User(role=Role.USER)))
    assert exc.value.status_code == 403


def test_require_role_accepte_le_bon_role():
    checker = require_role(Role.ADMIN)
    admin = User(role=Role.ADMIN)
    assert asyncio.run(checker(admin)) is admin
