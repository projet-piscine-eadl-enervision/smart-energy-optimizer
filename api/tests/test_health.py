"""Routes /health et /health/mock (l'API Mock est simulée, aucun appel réseau)."""
import httpx2
import pytest

from app.api.routes import health
from app.core.config import settings


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["environment"] == settings.APP_ENV
    assert set(body["version"]) == {"commit", "sha"}


@pytest.fixture
def mock_api(monkeypatch):
    """Fait répondre l'API Mock par une fonction de test au lieu du réseau."""

    def _mock_api(handler):
        vrai_client = httpx2.AsyncClient

        def faux_client(**kwargs):
            return vrai_client(transport=httpx2.MockTransport(handler), **kwargs)

        monkeypatch.setattr(health.httpx2, "AsyncClient", faux_client)

    return _mock_api


def test_health_mock_ok(client, mock_api):
    mock_api(lambda request: httpx2.Response(200, json={"status": "ok"}))
    response = client.get("/health/mock")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_mock_injoignable(client, mock_api):
    def handler(request):
        raise httpx2.ConnectError("connexion refusée", request=request)

    mock_api(handler)
    response = client.get("/health/mock")
    assert response.status_code == 503
    assert response.json()["detail"] == "API Mock inaccessible"


def test_health_mock_en_erreur(client, mock_api):
    mock_api(lambda request: httpx2.Response(500))
    response = client.get("/health/mock")
    assert response.status_code == 502
    assert "500" in response.json()["detail"]


def test_metrics(client):
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
    # /health n'est pas comptée : les sondes fausseraient les statistiques de trafic
    assert 'handler="/health"' not in response.text


def test_health_mock_missing_url(client, monkeypatch):
    monkeypatch.setattr(health, "MOCK_API_URL", "")
    response = client.get("/health/mock")
    assert response.status_code == 503
    assert response.json()["detail"] == "MOCK_API_URL non configurée"
