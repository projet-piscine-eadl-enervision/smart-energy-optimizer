"""Hachage des mots de passe et jetons JWT."""
from datetime import UTC, datetime, timedelta

import jwt

from app.core import security
from app.core.config import settings


def test_hash_ne_contient_pas_le_mot_de_passe():
    hashed = security.hash_password("motdepasse")
    assert hashed != "motdepasse"
    assert "motdepasse" not in hashed


def test_verify_password_correct():
    hashed = security.hash_password("motdepasse")
    assert security.verify_password("motdepasse", hashed)


def test_verify_password_incorrect():
    hashed = security.hash_password("motdepasse")
    assert not security.verify_password("mauvais", hashed)


def test_jeton_aller_retour():
    token = security.create_access_token(subject="42")
    assert security.decode_access_token(token) == "42"


def test_jeton_illisible():
    assert security.decode_access_token("pas-un-jeton") is None


def test_jeton_signe_avec_une_autre_cle():
    token = jwt.encode({"sub": "42"}, "autre-cle", algorithm=settings.ALGORITHM)
    assert security.decode_access_token(token) is None


def test_jeton_expire():
    expire = datetime.now(UTC) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "42", "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    assert security.decode_access_token(token) is None


def test_jeton_modifie():
    token = security.create_access_token(subject="42")
    entete, contenu, signature = token.split(".")
    falsifie = f"{entete}.{contenu}.{signature[::-1]}"
    assert security.decode_access_token(falsifie) is None
