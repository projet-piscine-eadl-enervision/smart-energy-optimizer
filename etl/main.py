from datetime import UTC, datetime

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from metrics import build_registry

# L'ETL n'expose pas d'API métier : pas de documentation, seulement la sonde de santé et les
# métriques lues par Prometheus (voir metrics.py)
app = FastAPI(title="enervision-etl", docs_url=None, redoc_url=None, openapi_url=None)
registry = build_registry()


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.get("/metrics")
def metrics():
    # Fonction synchrone : FastAPI la lance dans un thread, la requête psycopg ne bloque pas la boucle
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)
