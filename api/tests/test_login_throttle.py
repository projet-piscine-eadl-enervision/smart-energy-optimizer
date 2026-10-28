"""Protection de /auth/login contre la force brute : limites par IP et par e-mail, comptes désactivés,
casse de l'e-mail, journalisation, métrique et IP réelle derrière le proxy du frontend."""
import logging

import pytest
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from app import main
from app.api.deps import get_login_throttle
from app.api.routes import auth
from app.core.config import settings
from app.core.login_throttle import LoginThrottle, email_key, mask_email
from app.db.session import get_db

PASSWORD = "motdepasse"


def login(client, email="alice@example.com", password=PASSWORD):
    return client.post("/auth/login", data={"username": email, "password": password})


def as_ip(ip):
    """Client dont la connexion arrive de cette IP (les dépendances surchargées sont celles de app)."""
    return TestClient(main.app, client=(ip, 50000))


def attempts(outcome):
    return REGISTRY.get_sample_value("auth_login_attempts_total", {"outcome": outcome}) or 0


@pytest.fixture
def alice(make_user):
    return make_user(email="alice@example.com", password=PASSWORD)


# --- Limite par IP ---

def test_ip_is_blocked_after_max_failures(client, alice):
    for n in range(settings.LOGIN_IP_MAX_FAILURES):
        assert login(client, email=f"user{n}@example.com", password="mauvais").status_code == 401

    response = login(client)  # bon mot de passe, mais l'IP est bloquée
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(settings.LOGIN_IP_WINDOW_SECONDS)
    assert "access_token" not in response.json()


def test_ip_block_is_lifted_after_the_window(client, alice, clock):
    for n in range(settings.LOGIN_IP_MAX_FAILURES):
        login(client, email=f"user{n}@example.com", password="mauvais")
    clock.advance(seconds=settings.LOGIN_IP_WINDOW_SECONDS - 60)
    response = login(client)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"

    clock.advance(seconds=60)
    assert login(client).status_code == 200


def test_ip_window_is_sliding(client, alice, clock):
    # Un échec ancien sort de la fenêtre pendant que les récents y restent
    login(client, email="old@example.com", password="mauvais")
    clock.advance(seconds=600)
    for n in range(settings.LOGIN_IP_MAX_FAILURES - 1):
        login(client, email=f"user{n}@example.com", password="mauvais")
    assert login(client).status_code == 429

    clock.advance(seconds=settings.LOGIN_IP_WINDOW_SECONDS - 600)
    assert login(client).status_code == 200


def test_ip_limit_is_per_ip(client, alice):
    for n in range(settings.LOGIN_IP_MAX_FAILURES):
        login(client, email=f"user{n}@example.com", password="mauvais")
    assert login(client).status_code == 429
    assert login(as_ip("203.0.113.7")).status_code == 200


def test_blocked_attempt_skips_password_check(client, alice, monkeypatch):
    for n in range(settings.LOGIN_IP_MAX_FAILURES):
        login(client, email=f"user{n}@example.com", password="mauvais")
    calls = []
    monkeypatch.setattr(auth, "verify_password", lambda *args: calls.append(args) or True)
    assert login(client).status_code == 429
    assert calls == []


# --- Limite par e-mail ---

def test_account_is_locked_across_ips(client, alice):
    for n in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        assert login(as_ip(f"203.0.113.{n}"), password="mauvais").status_code == 401

    response = login(as_ip("198.51.100.1"))  # nouvelle IP, bon mot de passe
    assert response.status_code == 429
    assert response.headers["Retry-After"] == str(settings.LOGIN_ACCOUNT_WINDOW_SECONDS)


def test_account_lock_does_not_block_other_accounts(client, alice, make_user):
    make_user(email="bob@example.com", password=PASSWORD)
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        login(client, password="mauvais")
    assert login(client).status_code == 429
    assert login(client, email="bob@example.com").status_code == 200


def test_account_lock_is_lifted_after_the_window(client, alice, clock):
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        login(client, password="mauvais")
    clock.advance(seconds=settings.LOGIN_ACCOUNT_WINDOW_SECONDS)
    assert login(client).status_code == 200


def test_success_resets_account_failures(client, alice):
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES - 1):
        login(client, password="mauvais")
    assert login(client).status_code == 200

    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES - 1):
        assert login(client, password="mauvais").status_code == 401
    assert login(client).status_code == 200


def test_success_does_not_reset_ip_failures(client, alice):
    # L'attaquant ne peut pas vider le compteur de son IP en se connectant à son propre compte
    for n in range(settings.LOGIN_IP_MAX_FAILURES - 2):
        login(client, email=f"user{n}@example.com", password="mauvais")
    login(client, password="mauvais")
    assert login(client).status_code == 200

    login(client, email="last@example.com", password="mauvais")
    assert login(client).status_code == 429


def test_success_keeps_ip_failures_made_on_the_account(client, alice, failure_store):
    login(client, password="mauvais")
    assert login(client).status_code == 200
    assert [(ip, key) for ip, key, _ in failure_store.failures] == [("testclient", None)]


def test_lock_does_not_reveal_whether_account_exists(client, alice):
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        login(as_ip("203.0.113.1"), email="alice@example.com", password="mauvais")
        login(as_ip("203.0.113.2"), email="nobody@example.com", password="mauvais")

    known = login(as_ip("198.51.100.1"), email="alice@example.com", password="mauvais")
    unknown = login(as_ip("198.51.100.2"), email="nobody@example.com", password="mauvais")
    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()
    assert known.headers["Retry-After"] == unknown.headers["Retry-After"]


def test_account_failures_ignore_email_case(client, alice):
    for n in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        login(client, email="Alice@Example.com" if n % 2 else "ALICE@EXAMPLE.COM", password="mauvais")
    assert login(client).status_code == 429


def test_store_keeps_no_plain_email(client, failure_store):
    login(client, email="alice@example.com", password="mauvais")
    assert failure_store.failures[0][:2] == ("testclient", email_key("alice@example.com"))
    assert "alice" not in failure_store.failures[0][1]


# --- Compte désactivé ---

def test_inactive_account_gets_generic_401(client, make_user):
    make_user(email="alice@example.com", password=PASSWORD, is_active=False)
    response = login(client)
    assert response.status_code == 401
    assert response.json() == {"detail": "Email ou mot de passe incorrect"}
    assert "access_token" not in response.json()


def test_inactive_account_still_checks_the_password(client, make_user, monkeypatch):
    user = make_user(email="alice@example.com", password=PASSWORD, is_active=False)
    calls = []

    def spy(plain, hashed):
        calls.append(hashed)
        return True

    monkeypatch.setattr(auth, "verify_password", spy)
    assert login(client).status_code == 401
    assert calls == [user.hashed_password]


def test_inactive_account_counts_as_failure(client, make_user):
    make_user(email="alice@example.com", password=PASSWORD, is_active=False)
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        login(client)
    assert login(client).status_code == 429


# --- Casse de l'e-mail ---

def test_login_ignores_email_case(client, alice):
    assert login(client, email="  Alice@Example.COM ").status_code == 200


def test_register_stores_email_in_lowercase(client):
    response = client.post("/auth/register", json={"email": "Bob@Example.com", "password": PASSWORD})
    assert response.status_code == 201
    assert response.json()["email"] == "bob@example.com"
    assert login(client, email="BOB@example.com").status_code == 200


def test_register_rejects_same_email_with_other_case(client, alice):
    response = client.post("/auth/register", json={"email": "ALICE@example.com", "password": PASSWORD})
    assert response.status_code == 409


# --- Journalisation et métrique ---

def test_failure_is_logged_without_password(client, alice, caplog):
    caplog.set_level(logging.INFO, logger="app")
    login(client, email="Alice@example.com", password="secret-a-ne-pas-logguer")
    record = next(r for r in caplog.records if "login failed" in r.getMessage())
    message = record.getMessage()
    assert record.levelno == logging.WARNING
    assert "reason=invalid_credentials" in message
    assert "ip=testclient" in message
    assert "a***@example.com" in message
    assert "alice@example.com" not in message
    assert "secret-a-ne-pas-logguer" not in caplog.text


def test_block_is_logged(client, caplog):
    caplog.set_level(logging.INFO, logger="app")
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES + 1):
        login(client, password="mauvais")
    messages = [r.getMessage() for r in caplog.records]
    assert any("login blocked reason=account" in m and "retry_after=" in m for m in messages)


def test_outcomes_are_counted(client, alice, make_user):
    make_user(email="off@example.com", password=PASSWORD, is_active=False)
    before = {o: attempts(o) for o in ("success", "invalid_credentials", "inactive_account", "account_blocked")}

    login(client)
    for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
        login(client, password="mauvais")
    login(client)
    login(client, email="off@example.com")

    assert attempts("success") == before["success"] + 1
    assert attempts("invalid_credentials") == before["invalid_credentials"] + settings.LOGIN_ACCOUNT_MAX_FAILURES
    assert attempts("account_blocked") == before["account_blocked"] + 1
    assert attempts("inactive_account") == before["inactive_account"] + 1


def test_metric_is_exposed(client):
    assert "auth_login_attempts_total" in client.get("/metrics").text


def test_mask_email():
    assert mask_email("Alice@Example.com") == "a***@example.com"
    assert mask_email("pas-un-email") == "***"
    # Pas de retour à la ligne forgé dans les logs
    assert mask_email("a@x.fr\nlogin succeeded") == "a***@x.fr?login?succeeded"


# --- IP réelle derrière le proxy du frontend ---

@pytest.fixture
def proxied_app(monkeypatch, db, failure_store, clock):
    """Application dont le proxy de confiance est le réseau 172.18.0.0/16 (réseau Docker)."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_IPS", "172.18.0.0/16")
    application = main.create_app()

    async def override_get_db():
        yield db

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_login_throttle] = lambda: LoginThrottle(failure_store, now=clock)
    return application


def test_trusted_proxy_gives_separate_counters(proxied_app, failure_store):
    proxy = TestClient(proxied_app, client=("172.18.0.5", 50000))
    for n in range(settings.LOGIN_IP_MAX_FAILURES):
        proxy.post(
            "/auth/login",
            data={"username": f"user{n}@example.com", "password": "mauvais"},
            headers={"X-Forwarded-For": "203.0.113.10"},
        )
    assert {ip for ip, _, _ in failure_store.failures} == {"203.0.113.10"}

    blocked = proxy.post(
        "/auth/login", data={"username": "x@example.com", "password": "mauvais"},
        headers={"X-Forwarded-For": "203.0.113.10"},
    )
    other = proxy.post(
        "/auth/login", data={"username": "x@example.com", "password": "mauvais"},
        headers={"X-Forwarded-For": "203.0.113.11"},
    )
    assert blocked.status_code == 429
    assert other.status_code == 401


def test_trusted_proxy_keeps_the_address_it_added(proxied_app, failure_store):
    # Le client a forgé un X-Forwarded-For ; le proxy y a ajouté l'adresse réelle, à droite
    proxy = TestClient(proxied_app, client=("172.18.0.5", 50000))
    proxy.post(
        "/auth/login", data={"username": "x@example.com", "password": "mauvais"},
        headers={"X-Forwarded-For": "1.2.3.4, 203.0.113.10"},
    )
    assert failure_store.failures[0][0] == "203.0.113.10"


def test_untrusted_peer_cannot_spoof_its_ip(proxied_app, failure_store):
    direct = TestClient(proxied_app, client=("198.51.100.9", 50000))
    direct.post(
        "/auth/login", data={"username": "x@example.com", "password": "mauvais"},
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert failure_store.failures[0][0] == "198.51.100.9"


def test_forwarded_for_is_ignored_by_default(client, failure_store):
    client.post(
        "/auth/login", data={"username": "x@example.com", "password": "mauvais"},
        headers={"X-Forwarded-For": "1.2.3.4"},
    )
    assert failure_store.failures[0][0] == "testclient"
