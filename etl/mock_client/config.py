import os

from dotenv import load_dotenv

load_dotenv()

MOCK_API_URL_MISSING = (
    "MOCK_API_URL manquante : renseignez l'URL de l'API Mock dans le .env "
    "(voir .env.example)"
)


def read_mock_api_url() -> str:
    """URL de l'API Mock, obligatoire : aucune adresse n'est codée en dur (Sonar S5332, S1313)."""
    url = (os.getenv("MOCK_API_URL") or "").strip().rstrip("/")
    if not url:
        raise RuntimeError(MOCK_API_URL_MISSING)
    return url


MOCK_API_URL = read_mock_api_url()
MOCK_API_USERNAME = os.getenv("MOCK_API_USERNAME")
MOCK_API_PASSWORD = os.getenv("MOCK_API_PASSWORD")
