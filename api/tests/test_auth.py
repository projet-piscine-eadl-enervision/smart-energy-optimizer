"""Inscription, connexion et profil courant (/auth/*)."""
from app.core.security import create_access_token


def test_register(client):
    response = client.post(
        "/auth/register", json={"email": "bob@example.com", "password": "motdepasse"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert body["role"] == "user"
    assert "hashed_password" not in body
    assert "password" not in body


def test_register_email_deja_utilise(client, make_user):
    make_user(email="bob@example.com")
    response = client.post(
        "/auth/register", json={"email": "bob@example.com", "password": "motdepasse"}
    )
    assert response.status_code == 409


def test_register_mot_de_passe_trop_court(client):
    response = client.post(
        "/auth/register", json={"email": "bob@example.com", "password": "court"}
    )
    assert response.status_code == 422


def test_register_ne_permet_pas_de_devenir_admin(client):
    response = client.post(
        "/auth/register",
        json={"email": "bob@example.com", "password": "motdepasse", "role": "admin"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "user"


def test_login(client, make_user):
    make_user(email="alice@example.com", password="motdepasse")
    response = client.post(
        "/auth/login", data={"username": "alice@example.com", "password": "motdepasse"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_mauvais_mot_de_passe(client, make_user):
    make_user(email="alice@example.com", password="motdepasse")
    response = client.post(
        "/auth/login", data={"username": "alice@example.com", "password": "mauvais"}
    )
    assert response.status_code == 401


def test_login_email_inconnu(client):
    response = client.post(
        "/auth/login", data={"username": "inconnu@example.com", "password": "motdepasse"}
    )
    assert response.status_code == 401


def test_me(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"


def test_me_sans_jeton(client):
    assert client.get("/auth/me").status_code == 401


def test_me_jeton_invalide(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer faux"})
    assert response.status_code == 401


def test_me_utilisateur_supprime(client):
    token = create_access_token(subject="999")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_utilisateur_desactive(client, make_user):
    user = make_user(is_active=False)
    token = create_access_token(subject=str(user.id))
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_register_mot_de_passe_de_72_octets(client):
    response = client.post(
        "/auth/register", json={"email": "bob@example.com", "password": "a" * 72}
    )
    assert response.status_code == 201


def test_register_mot_de_passe_trop_long(client):
    response = client.post(
        "/auth/register", json={"email": "bob@example.com", "password": "a" * 73}
    )
    assert response.status_code == 422


def test_register_mot_de_passe_trop_long_en_octets(client):
    # 37 caractères de 2 octets : 74 octets
    response = client.post(
        "/auth/register", json={"email": "bob@example.com", "password": "é" * 37}
    )
    assert response.status_code == 422


def test_login_mot_de_passe_trop_long(client, make_user):
    make_user(email="bob@example.com")
    response = client.post(
        "/auth/login", data={"username": "bob@example.com", "password": "a" * 100}
    )
    assert response.status_code == 401
