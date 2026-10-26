"""Configuration : les valeurs de l'API Mock viennent des variables d'environnement."""
import importlib

import pytest

from mock_client import config


def test_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("MOCK_API_URL", "https://autre-mock.test")
    monkeypatch.setenv("MOCK_API_USERNAME", "bob")
    monkeypatch.setenv("MOCK_API_PASSWORD", "mdp")
    try:
        importlib.reload(config)
        assert config.MOCK_API_URL == "https://autre-mock.test"
        assert config.MOCK_API_USERNAME == "bob"
        assert config.MOCK_API_PASSWORD == "mdp"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_url_without_trailing_slash(monkeypatch):
    monkeypatch.setenv("MOCK_API_URL", "https://mock.test/")
    try:
        importlib.reload(config)
        assert config.MOCK_API_URL == "https://mock.test"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_missing_url_raises_clear_error(monkeypatch):
    monkeypatch.delenv("MOCK_API_URL", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    try:
        with pytest.raises(RuntimeError, match="MOCK_API_URL manquante"):
            importlib.reload(config)
    finally:
        monkeypatch.undo()
        importlib.reload(config)
