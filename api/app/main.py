"""Point d'entrée de l'API EnerVision.

Assemble les routes et verrouille le CORS sur le front Angular. Le schéma de la base n'est
pas créé ici : il vient des migrations de db/migrations (dbmate), appliquées avant le
démarrage de l'API.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.routes import auth, health, history, predictions, recommendations
from app.core.config import settings

STATIC_DIR = Path(__file__).parent / "static"
FAVICON_URL = "/static/logoSmartEnergyOptimizer.ico"


def create_app() -> FastAPI:
    is_production = settings.APP_ENV == "production"

    # Les pages /docs et /redoc par défaut sont toujours désactivées : en production,
    # elles ne sont pas exposées, ailleurs elles sont redéfinies plus bas avec le favicon.
    application = FastAPI(
        title="Smart Energy Optimizer API",
        description=f"Environment : {settings.APP_ENV}",
        docs_url=None,
        redoc_url=None,
        openapi_url=None if is_production else "/openapi.json",
    )

    # CORS verrouillé sur l'origine du front — pas de "*" en présence de cookies/JWT
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if not is_production:
        application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

        @application.get("/docs", include_in_schema=False)
        async def swagger_ui():
            return get_swagger_ui_html(
                openapi_url=application.openapi_url,
                title=f"{application.title} - Swagger UI",
                swagger_favicon_url=FAVICON_URL,
            )

        @application.get("/redoc", include_in_schema=False)
        async def redoc():
            return get_redoc_html(
                openapi_url=application.openapi_url,
                title=f"{application.title} - ReDoc",
                redoc_favicon_url=FAVICON_URL,
            )

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(predictions.router)
    application.include_router(history.router)
    application.include_router(recommendations.router)

    # /metrics : requêtes, latence et codes de retour, pour Prometheus. Jamais exposée au public :
    # le proxy du frontend la refuse, Prometheus lit l'API en direct sur le réseau Docker.
    Instrumentator(excluded_handlers=["/health.*", "/metrics"]).instrument(application).expose(application)
    return application


app = create_app()
