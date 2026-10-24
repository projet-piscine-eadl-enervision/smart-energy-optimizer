"""Primitives de sécurité : hachage de mots de passe et jetons JWT.

On ne stocke JAMAIS un mot de passe en clair — seulement son hash bcrypt.
Les jetons sont signés avec SECRET_KEY : impossible à forger sans la clé.
"""
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# bcrypt (et non argon2) pour rester compatible avec les hashes déjà en base.
password_hash = PasswordHash((BcryptHasher(),))

# bcrypt ne lit que 72 octets et refuse davantage : on rejette plus tôt au lieu de tronquer
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode()) > MAX_PASSWORD_BYTES:
        return False
    return password_hash.verify(plain, hashed)


def create_access_token(subject: str) -> str:
    """Crée un JWT dont le 'sub' est l'identifiant de l'utilisateur."""
    expire = datetime.now(UTC) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Renvoie le 'sub' si le jeton est valide, sinon None."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None
