"""Documentation interactive : ouverte en dev et staging, fermée en production."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import create_app

DOC_PATHS = ["/docs", "/redoc", "/openapi.json"]


@pytest.mark.parametrize("env", ["dev", "staging"])
@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_ouvertes_hors_production(monkeypatch, env, path):
    monkeypatch.setattr(settings, "APP_ENV", env)
    assert TestClient(create_app()).get(path).status_code == 200


@pytest.mark.parametrize("path", DOC_PATHS)
def test_docs_fermees_en_production(monkeypatch, path):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert TestClient(create_app()).get(path).status_code == 404


def test_health_reste_ouvert_en_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    assert TestClient(create_app()).get("/health").status_code == 200
