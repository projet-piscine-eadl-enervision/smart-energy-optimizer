FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Utilisateur non-root pour exécuter l'API
RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --no-create-home app

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# Version affichée par /health, passée par la CI à la construction
ARG GIT_TITLE=dev
ARG GIT_SHA=dev
ENV GIT_TITLE=$GIT_TITLE \
    GIT_SHA=$GIT_SHA

USER app

EXPOSE 8000

# Sonde d'état : /health ne dépend pas de l'API Mock
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
