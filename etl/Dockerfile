FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Utilisateur non-root pour exécuter l'ETL
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --no-create-home app

WORKDIR /app

COPY requirements.txt .
# pip est retiré après l'installation : inutile à l'exécution, et ses copies embarquées
# (certifi, urllib3, msgpack...) déclenchent des alertes Trivy sans rapport avec nos dépendances
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y pip

COPY --chown=app:app . .

USER app

EXPOSE 8000

# Sonde d'état : /health ne dépend pas de l'API Mock
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
