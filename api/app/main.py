"""Point d'entrée de l'API EnerVision.

Assemble les routes et verrouille le CORS sur le front Angular. Le schéma de la base n'est
pas créé ici : il vient des migrations de db/migrations (dbmate), appliquées avant le
démarrage de l'API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health, history, predictions, recommendations
from app.core.config import settings

# En production, ni la documentation interactive ni le schéma OpenAPI ne sont exposés
NO_DOCS = {"docs_url": None, "redoc_url": None, "openapi_url": None}


def create_app() -> FastAPI:
    application = FastAPI(
        title="enervision-api",
        description=f"Environnement : {settings.APP_ENV}",
        **(NO_DOCS if settings.APP_ENV == "production" else {}),
    )

    # CORS verrouillé sur l'origine du front — pas de "*" en présence de cookies/JWT
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(predictions.router)
    application.include_router(history.router)
    application.include_router(recommendations.router)
    return application


app = create_app()
