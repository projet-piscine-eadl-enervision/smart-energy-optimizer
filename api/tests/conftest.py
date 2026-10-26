"""Fixtures communes aux tests unitaires de l'API.

Les tests ne demandent ni base de données ni réseau :
- les variables obligatoires reçoivent des valeurs de test avant tout import de l'application ;
- la session SQLAlchemy est remplacée par une fausse session en mémoire ;
- le TestClient est utilisé sans bloc `with`, donc le lifespan (create_all sur la base) ne tourne pas.
"""
import os
from datetime import UTC, datetime

# À faire avant d'importer app.* : Settings() est instancié à l'import de app.core.config
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SECRET_KEY", "cle-de-test-uniquement-de-32-octets-au-moins")

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models.user import Role, User


class FakeSession:
    """Remplace AsyncSession : stocke les utilisateurs dans un dictionnaire."""

    def __init__(self):
        self.users: dict[int, User] = {}

    async def get(self, model, user_id):
        return self.users.get(user_id)

    async def scalar(self, statement):
        # Les routes ne font qu'un select(User).where(User.email == ...) : on récupère l'email
        email = next(iter(statement.compile().params.values()))
        return next((u for u in self.users.values() if u.email == email), None)

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


@pytest.fixture
def db():
    return FakeSession()


@pytest.fixture
def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
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


@pytest.fixture
def auth_headers(make_user):
    user = make_user()
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}
