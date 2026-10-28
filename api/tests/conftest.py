"""Fixtures communes aux tests unitaires de l'API.

Les tests ne demandent ni base de données ni réseau :
- les variables obligatoires reçoivent des valeurs de test avant tout import de l'application ;
- la session SQLAlchemy est remplacée par une fausse session en mémoire ;
- le TestClient est utilisé sans bloc `with`, donc le lifespan (create_all sur la base) ne tourne pas.
"""
import os
from datetime import UTC, datetime, timedelta

# À faire avant d'importer app.* : Settings() est instancié à l'import de app.core.config
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "cle-de-test-uniquement-de-32-octets-au-moins")
os.environ.setdefault("MOCK_API_URL", "https://mock.test")

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_login_throttle
from app.core.login_throttle import LoginThrottle
from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.user import Role, User


class FakeResult:
    """Résultat d'execute() : itérable, et first() comme un vrai résultat SQLAlchemy."""

    def __init__(self, rows: list):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    """Remplace AsyncSession : stocke les utilisateurs dans un dictionnaire."""

    def __init__(self):
        self.users: dict[int, User] = {}
        self.rows: list = []  # lignes renvoyées par execute()
        self.executed: list[tuple[str, dict]] = []  # requêtes reçues, pour les vérifier

    async def get(self, model, user_id):
        return self.users.get(user_id)

    async def scalar(self, statement):
        # Les routes ne font qu'un select(User).where(User.email == ...) : on récupère l'email
        email = next(iter(statement.compile().params.values()))
        return next((u for u in self.users.values() if u.email == email), None)

    async def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))
        return FakeResult(self.rows)

    def add(self, user: User):
        # Valeurs que la base remplirait elle-même à l'insertion
        user.id = len(self.users) + 1
        user.is_active = True if user.is_active is None else user.is_active
        user.role = user.role or Role.USER
        user.created_at = datetime.now(UTC)
        self.users[user.id] = user

    async def commit(self):
        pass

    async def refresh(self, user):
        pass


class MemoryFailureStore:
    """Remplace app.login_failure : mêmes opérations que SqlFailureStore, en mémoire."""

    def __init__(self):
        self.failures: list[tuple[str, str, datetime]] = []  # (ip, email_key, date)

    def _recent(self, match, since, limit):
        dates = sorted((at for *keys, at in self.failures if match(*keys) and at > since), reverse=True)
        return dates[:limit]

    async def recent_ip_failures(self, ip, since, limit):
        return self._recent(lambda i, _k: i == ip, since, limit)

    async def recent_email_failures(self, key, since, limit):
        return self._recent(lambda _i, k: k == key, since, limit)

    async def add_failure(self, ip, key, at, purge_before):
        self.failures = [f for f in self.failures if f[2] >= purge_before]
        self.failures.append((ip, key, at))

    async def clear_email(self, key):
        # Comme en base : l'échec reste compté pour l'IP, il n'est plus lié à l'e-mail
        self.failures = [(ip, None if k == key else k, at) for ip, k, at in self.failures]


class Clock:
    """Heure contrôlée par le test : clock.advance(seconds=...) fait avancer le temps."""

    def __init__(self):
        self.current = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.current

    def advance(self, **delta):
        self.current += timedelta(**delta)


@pytest.fixture
def db():
    return FakeSession()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def failure_store():
    return MemoryFailureStore()


@pytest.fixture
def client(db, failure_store, clock):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_login_throttle] = lambda: LoginThrottle(failure_store, now=clock)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_user(db):
    """Crée un utilisateur directement dans la fausse base."""

    def _make_user(email="alice@example.com", password="motdepasse", **kwargs):
        user = User(email=email, hashed_password=hash_password(password), **kwargs)
        db.add(user)
        return user

    return _make_user


def headers_for(user: User) -> dict:
    return {"Authorization": f"Bearer {create_access_token(subject=str(user.id))}"}


@pytest.fixture
def auth_headers(make_user):
    """Jeton d'un admin : il lit tous les sites, ce que vérifient les tests des routes de données."""
    return headers_for(make_user(role=Role.ADMIN))


@pytest.fixture
def user_headers(make_user):
    """Jeton d'un user rattaché à SITE001 : il ne lit que ce site."""
    return headers_for(make_user(email="bob@example.com", role=Role.USER, site_id="SITE001"))
