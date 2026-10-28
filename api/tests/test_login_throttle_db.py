"""Compteurs d'échecs de /auth/login dans app.login_failure, contre TimescaleDB migrée.

Ignorés sans base (adresse de test de conftest). En CI, le job python démarre la base migrée.
Les lignes de test utilisent l'IP 192.0.2.250 (réservée à la documentation) et sont supprimées.
"""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import settings
from app.core.login_throttle import LoginThrottle, SqlFailureStore, email_key

pytestmark = pytest.mark.skipif(
    settings.DATABASE_URL.endswith("@localhost:5432/test"),
    reason="DATABASE_URL de test : pas de base",
)

IP = "192.0.2.250"
EMAIL = "throttle-db-test@example.com"
OTHER_EMAIL = "throttle-db-other@example.com"


def run(check):
    async def main():
        engine = create_async_engine(settings.DATABASE_URL)
        cleanup = text("DELETE FROM app.login_failure WHERE ip = :ip")
        async with engine.begin() as conn:
            await conn.execute(cleanup, {"ip": IP})
        try:
            async with AsyncSession(engine) as session:
                await check(session)
        finally:
            async with engine.begin() as conn:
                await conn.execute(cleanup, {"ip": IP})
            await engine.dispose()

    asyncio.run(main())


def test_failures_are_read_newest_first_and_limited():
    async def check(session):
        store = SqlFailureStore(session)
        now = datetime.now(UTC)
        dates = [now - timedelta(minutes=m) for m in (3, 1, 2)]
        for at in dates:
            await store.add_failure(IP, email_key(EMAIL), at, purge_before=now - timedelta(hours=1))

        assert await store.recent_ip_failures(IP, now - timedelta(minutes=10), 2) == sorted(dates, reverse=True)[:2]
        assert len(await store.recent_email_failures(email_key(EMAIL), now - timedelta(minutes=10), 10)) == 3
        # Fenêtre plus courte : l'échec d'il y a 3 minutes n'en fait plus partie
        assert len(await store.recent_ip_failures(IP, now - timedelta(seconds=150), 10)) == 2

    run(check)


def test_clear_email_keeps_other_emails():
    async def check(session):
        store = SqlFailureStore(session)
        now = datetime.now(UTC)
        await store.add_failure(IP, email_key(EMAIL), now, purge_before=now - timedelta(hours=1))
        await store.add_failure(IP, email_key(OTHER_EMAIL), now, purge_before=now - timedelta(hours=1))

        await store.clear_email(email_key(EMAIL))

        since = now - timedelta(minutes=1)
        assert await store.recent_email_failures(email_key(EMAIL), since, 10) == []
        assert len(await store.recent_email_failures(email_key(OTHER_EMAIL), since, 10)) == 1
        assert len(await store.recent_ip_failures(IP, since, 10)) == 2

    run(check)


def test_old_failures_are_purged():
    async def check(session):
        store = SqlFailureStore(session)
        now = datetime.now(UTC)
        old = now - timedelta(hours=2)
        await store.add_failure(IP, email_key(EMAIL), old, purge_before=old - timedelta(hours=1))
        await store.add_failure(IP, email_key(EMAIL), now, purge_before=now - timedelta(hours=1))

        count = await session.scalar(text("SELECT count(*) FROM app.login_failure WHERE ip = :ip"), {"ip": IP})
        assert count == 1

    run(check)


def test_throttle_blocks_account_with_shared_counters():
    # Deux instances de l'API = deux LoginThrottle sur deux sessions : elles voient les mêmes échecs
    async def check(session):
        first = LoginThrottle(SqlFailureStore(session))
        for _ in range(settings.LOGIN_ACCOUNT_MAX_FAILURES):
            await first.record_failure(IP, EMAIL)

        async with AsyncSession(session.bind) as other_session:
            second = LoginThrottle(SqlFailureStore(other_session))
            block = await second.check("192.0.2.251", EMAIL)
            assert block is not None
            assert block.reason == "account"
            assert 0 < block.retry_after <= settings.LOGIN_ACCOUNT_WINDOW_SECONDS

            await second.record_success(EMAIL)
            assert await first.check("192.0.2.251", EMAIL) is None

    run(check)
