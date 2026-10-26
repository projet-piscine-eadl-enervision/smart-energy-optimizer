"""Santé de l'API et de l'API Mock. Utilisées par le staging et le workflow de release."""
from datetime import UTC, datetime

import httpx2
from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(prefix="/health", tags=["health"])

# Aucune adresse codée en dur (Sonar S5332, S1313) : l'URL vient uniquement de la configuration
MOCK_API_URL = settings.MOCK_API_URL.strip().rstrip("/")
MOCK_API_CREDENTIALS = (settings.MOCK_API_USERNAME, settings.MOCK_API_PASSWORD)
# Authentification basique requise sur l'URL publique, absente sur le réseau de l'école
MOCK_API_AUTH = MOCK_API_CREDENTIALS if all(MOCK_API_CREDENTIALS) else None


@router.get("", summary="Service health check")
async def health():
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "timestamp": datetime.now(UTC).isoformat(),
        "version": {"commit": settings.GIT_TITLE, "sha": settings.GIT_SHA},
    }


@router.get("/mock", summary="Mock service health check",
            responses={503: {"description": "API Mock inaccessible ou mal configurée"},
                       502: {"description": "Erreur de l'API Mock"},})
async def health_mock():
    if not MOCK_API_URL:
        raise HTTPException(status_code=503, detail="MOCK_API_URL non configurée")

    try:
        async with httpx2.AsyncClient(timeout=5.0, auth=MOCK_API_AUTH) as client:
            response = await client.get(f"{MOCK_API_URL}/health")
            response.raise_for_status()
            return response.json()

    except httpx2.RequestError:
        raise HTTPException(status_code=503, detail="API Mock inaccessible")

    except httpx2.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502, detail=f"Erreur API Mock : {exc.response.status_code}"
        )
