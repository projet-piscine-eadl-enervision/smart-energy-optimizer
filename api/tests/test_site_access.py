"""Accès aux sites selon le rôle : un admin lit tous les sites, un user seulement le sien."""
import pytest
from fastapi import HTTPException

from app.api.deps import site_scope
from app.core.security import create_access_token
from app.models.user import Role, User


def headers_for(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


def test_admin_reads_the_requested_site_or_all_sites():
    admin = User(role=Role.ADMIN)
    assert site_scope(admin, "SITE002") == "SITE002"
    assert site_scope(admin, None) is None


def test_user_is_limited_to_their_site():
    user = User(role=Role.USER, site_id="SITE001")
    assert site_scope(user, None) == "SITE001"
    assert site_scope(user, "SITE001") == "SITE001"
    with pytest.raises(HTTPException) as refused:
        site_scope(user, "SITE002")
    assert refused.value.status_code == 403


def test_user_without_site_has_no_access():
    with pytest.raises(HTTPException) as refused:
        site_scope(User(role=Role.USER, site_id=None), None)
    assert refused.value.status_code == 403


def test_user_history_without_site_is_their_site_not_the_total(client, db, user_headers):
    response = client.get("/history", headers=user_headers)

    assert response.status_code == 200
    _, params = db.executed[0]
    assert params["site_id"] == "SITE001"


def test_admin_history_without_site_is_the_total(client, db, auth_headers):
    client.get("/history", headers=auth_headers)

    _, params = db.executed[0]
    assert "site_id" not in params


@pytest.mark.parametrize(
    "url",
    [
        "/history?site_id=SITE002",
        "/predictions?site_id=SITE002",
        "/predictions/peaks?site_id=SITE002",
        "/alerts?site_id=SITE002",
        "/recommendations?site_id=SITE002",
        "/sites/SITE002/consumption",
        "/sites/SITE002/quality",
    ],
)
def test_user_cannot_read_another_site(client, db, user_headers, url):
    response = client.get(url, headers=user_headers)

    assert response.status_code == 403
    assert db.executed == []  # refusé avant toute requête


@pytest.mark.parametrize("url", ["/history", "/predictions", "/alerts", "/recommendations", "/sites"])
def test_user_without_site_is_refused(client, make_user, url):
    headers = headers_for(make_user(email="carol@example.com", role=Role.USER))

    assert client.get(url, headers=headers).status_code == 403


def test_user_lists_only_their_site(client, db, user_headers):
    client.get("/sites", headers=user_headers)

    _, params = db.executed[0]
    assert params == {"site_id": "SITE001"}


def test_admin_lists_all_sites(client, db, auth_headers):
    client.get("/sites", headers=auth_headers)

    _, params = db.executed[0]
    assert params == {"site_id": None}


def test_user_reads_their_own_site_details(client, db, user_headers):
    db.rows = []

    response = client.get("/sites/SITE001/quality", headers=user_headers)

    # la fausse base ne connaît aucun site : 404, mais la vérification des droits est passée
    assert response.status_code == 404


def test_profile_shows_the_site(client, user_headers):
    body = client.get("/auth/me", headers=user_headers).json()

    assert body["role"] == "user"
    assert body["site_id"] == "SITE001"
