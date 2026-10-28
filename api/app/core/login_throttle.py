"""Limitation des tentatives sur /auth/login, contre la force brute et le bourrage d'identifiants.

Deux limites, chacune sur une fenêtre glissante :
- par IP : au-delà de LOGIN_IP_MAX_FAILURES échecs, l'IP reçoit 429 ;
- par e-mail : au-delà de LOGIN_ACCOUNT_MAX_FAILURES échecs, toutes IP confondues, l'e-mail est bloqué,
  même avec le bon mot de passe. La clé est l'e-mail saisi, que le compte existe ou non : la réponse
  ne révèle pas quels comptes existent.

Les échecs sont stockés en base (app.login_failure) pour que plusieurs instances de l'API partagent
les mêmes compteurs. Une connexion réussie remet à zéro le compteur de l'e-mail, pas celui de l'IP.
"""
import hashlib
import hmac
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

_UNSAFE_LOG_CHARS = re.compile(r"[^a-z0-9.@*_+-]")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_key(email: str) -> str:
    """HMAC de l'e-mail normalisé : sert de clé sans garder l'adresse en clair."""
    digest = hmac.new(settings.SECRET_KEY.encode(), normalize_email(email).encode(), hashlib.sha256)
    return digest.hexdigest()


def mask_email(email: str) -> str:
    """alice@example.com -> a***@example.com, pour les logs.

    Les caractères inattendus deviennent « ? » : un e-mail saisi ne peut pas forger de ligne de log.
    """
    local, _, domain = normalize_email(email).partition("@")
    if not domain:
        return "***"
    return _UNSAFE_LOG_CHARS.sub("?", f"{local[:1]}***@{domain[:100]}")


class FailureStore(Protocol):
    """Lecture et écriture des échecs. Les dates renvoyées vont de la plus récente à la plus ancienne."""

    async def recent_ip_failures(self, ip: str, since: datetime, limit: int) -> list[datetime]: ...

    async def recent_email_failures(self, key: str, since: datetime, limit: int) -> list[datetime]: ...

    async def add_failure(self, ip: str, key: str, at: datetime, purge_before: datetime) -> None: ...

    async def clear_email(self, key: str) -> None: ...


RECENT_BY_IP = text(
    "SELECT created_at FROM app.login_failure WHERE ip = :value AND created_at > :since "
    "ORDER BY created_at DESC LIMIT :limit"
)
RECENT_BY_EMAIL = text(
    "SELECT created_at FROM app.login_failure WHERE email_key = :value AND created_at > :since "
    "ORDER BY created_at DESC LIMIT :limit"
)
INSERT_FAILURE = text("INSERT INTO app.login_failure (ip, email_key, created_at) VALUES (:ip, :key, :at)")
PURGE_FAILURES = text("DELETE FROM app.login_failure WHERE created_at < :before")
# Les échecs restent comptés pour l'IP : seul le lien avec l'e-mail est retiré
CLEAR_EMAIL = text("UPDATE app.login_failure SET email_key = NULL WHERE email_key = :key")


class SqlFailureStore:
    """Stockage dans app.login_failure, avec la session de la requête."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _recent(self, statement, value: str, since: datetime, limit: int) -> list[datetime]:
        result = await self.db.execute(statement, {"value": value, "since": since, "limit": limit})
        return [row[0] for row in result]

    async def recent_ip_failures(self, ip: str, since: datetime, limit: int) -> list[datetime]:
        return await self._recent(RECENT_BY_IP, ip, since, limit)

    async def recent_email_failures(self, key: str, since: datetime, limit: int) -> list[datetime]:
        return await self._recent(RECENT_BY_EMAIL, key, since, limit)

    async def add_failure(self, ip: str, key: str, at: datetime, purge_before: datetime) -> None:
        await self.db.execute(INSERT_FAILURE, {"ip": ip, "key": key, "at": at})
        # Purge des lignes qui ne comptent plus dans aucune fenêtre : la table reste petite
        await self.db.execute(PURGE_FAILURES, {"before": purge_before})
        await self.db.commit()

    async def clear_email(self, key: str) -> None:
        await self.db.execute(CLEAR_EMAIL, {"key": key})
        await self.db.commit()


@dataclass(frozen=True)
class Block:
    """Tentative refusée avant tout contrôle du mot de passe."""

    reason: str  # "ip" ou "account"
    retry_after: int  # secondes


def _block_end(failures: list[datetime], max_failures: int, window: timedelta) -> datetime | None:
    """Fin du blocage si la fenêtre contient au moins max_failures échecs, sinon None.

    Le blocage dure jusqu'à ce que le plus ancien de ces échecs sorte de la fenêtre.
    """
    if len(failures) < max_failures:
        return None
    return failures[max_failures - 1] + window


class LoginThrottle:
    def __init__(self, store: FailureStore, now: Callable[[], datetime] | None = None):
        self.store = store
        self.now = now or (lambda: datetime.now(UTC))
        self.ip_max = settings.LOGIN_IP_MAX_FAILURES
        self.ip_window = timedelta(seconds=settings.LOGIN_IP_WINDOW_SECONDS)
        self.account_max = settings.LOGIN_ACCOUNT_MAX_FAILURES
        self.account_window = timedelta(seconds=settings.LOGIN_ACCOUNT_WINDOW_SECONDS)

    async def check(self, ip: str, email: str) -> Block | None:
        """Renvoie le blocage en cours pour cette IP ou cet e-mail, ou None si la tentative est permise."""
        now = self.now()
        ip_failures = await self.store.recent_ip_failures(ip, now - self.ip_window, self.ip_max)
        end = _block_end(ip_failures, self.ip_max, self.ip_window)
        if end:
            return Block("ip", _seconds_until(end, now))

        key = email_key(email)
        account_failures = await self.store.recent_email_failures(key, now - self.account_window, self.account_max)
        end = _block_end(account_failures, self.account_max, self.account_window)
        if end:
            return Block("account", _seconds_until(end, now))
        return None

    async def record_failure(self, ip: str, email: str) -> None:
        now = self.now()
        purge_before = now - max(self.ip_window, self.account_window)
        await self.store.add_failure(ip, email_key(email), now, purge_before)

    async def record_success(self, email: str) -> None:
        await self.store.clear_email(email_key(email))


def _seconds_until(end: datetime, now: datetime) -> int:
    return max(1, math.ceil((end - now).total_seconds()))
