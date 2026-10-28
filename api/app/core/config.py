"""Configuration centralisée, lue depuis les variables d'environnement (.env).

Toutes les valeurs sensibles (DB, clé JWT) viennent d'ici — jamais en dur
dans le code. pydantic-settings valide et type automatiquement.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Environnement (dev, staging, production) : défini au lancement du conteneur, pas dans
    # l'image, car la même image est promue du staging vers la production
    APP_ENV: str = "dev"

    # Version déployée : renseignée à la construction de l'image par la CI (publish-images.yml)
    GIT_TITLE: str = "dev"
    GIT_SHA: str = "dev"

    # Base de données
    DATABASE_URL: str

    @field_validator("DATABASE_URL")
    @classmethod
    def use_async_driver(cls, url: str) -> str:
        # Les compose (local, staging) donnent postgresql://, partagé avec le service ml ;
        # l'API, asynchrone, a besoin du driver asyncpg
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Sécurité JWT
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Limitation des tentatives sur /auth/login (app/core/login_throttle.py) : échecs sur une fenêtre glissante
    LOGIN_IP_MAX_FAILURES: int = 10
    LOGIN_IP_WINDOW_SECONDS: int = 900
    LOGIN_ACCOUNT_MAX_FAILURES: int = 5
    LOGIN_ACCOUNT_WINDOW_SECONDS: int = 900

    # Proxys dont l'API accepte X-Forwarded-For pour connaître l'IP du client (IP ou réseaux CIDR, séparés
    # par des virgules). Vide : l'en-tête est ignoré et l'IP retenue est celle de la connexion.
    TRUSTED_PROXY_IPS: str = ""

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:4200"

    # API Mock, uniquement sondée par /health/mock (les données passent par l'ETL)
    MOCK_API_URL: str = ""
    MOCK_API_USERNAME: str | None = None
    MOCK_API_PASSWORD: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Mise en cache : les settings ne sont lus qu'une fois au démarrage."""
    return Settings()


settings = get_settings()
