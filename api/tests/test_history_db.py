"""Requêtes de /history contre TimescaleDB migrée.

Ignorés sans base (adresse de test de conftest). En CI, le job python démarre la base migrée.
Les sites SITE990 et SITE991 sont créés puis supprimés. Les relevés sont récents : l'agrégat horaire
les montre sans rafraîchissement (agrégation en temps réel).
"""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.routes.history import fetch_history
from app.core.config import settings

pytestmark = pytest.mark.skipif(
    settings.DATABASE_URL.endswith("@localhost:5432/test"),
    reason="DATABASE_URL de test : pas de base",
)

SITES = ("SITE990", "SITE991")
READING = text(
    "INSERT INTO core.energy_reading (time, mock_time, site_id, consumption_kw, data_quality, source) "
    "VALUES (:t, :t, :site, :kw, 'good', 'readings')"
)


async def clean(conn):
    await conn.execute(text("DELETE FROM core.energy_reading WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})
    await conn.execute(text("DELETE FROM ref.site WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})


async def with_database(check):
    """Sème trois heures passées et l'heure en cours, exécute check(session), puis nettoie."""
    engine = create_async_engine(settings.DATABASE_URL)
    hour = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    h3, h2, h1 = (hour - timedelta(hours=n) for n in (3, 2, 1))
    seeds = [
        # (heure, site, mesures) : h3 complète ; h2 à moitié manquante (gardée) ; h1 vide (écartée)
        (h3, "SITE990", [100, 100]), (h3, "SITE991", [50, 50]),
        (h2, "SITE990", [200, None]), (h2, "SITE991", [None, None]),
        (h1, "SITE990", [None, None]), (h1, "SITE991", [None, None]),
        (hour, "SITE990", [300]),  # heure en cours : exclue
    ]
    async with engine.begin() as conn:
        await clean(conn)
        others = (await conn.execute(text("SELECT site_id FROM ref.site"))).scalars().all()
        if others:
            await engine.dispose()
            pytest.skip("la base contient déjà des sites : le total ne se contrôle que sur une base vide")
        for site in SITES:
            await conn.execute(
                text("INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) VALUES (:s, 'Site de test', 'office', 500)"),
                {"s": site},
            )
        for start, site, values in seeds:
            for i, kw in enumerate(values):
                await conn.execute(READING, {"t": start + timedelta(minutes=10 * (i + 1)), "site": site, "kw": kw})
    try:
        async with AsyncSession(engine) as session:
            return await check(session), (h3, h2)
    finally:
        async with engine.begin() as conn:
            await clean(conn)
        await engine.dispose()


def test_history_of_one_site_drops_the_current_hour_and_empty_hours():
    async def check(session):
        return await fetch_history(session, 1, "SITE990")

    points, (h3, h2) = asyncio.run(with_database(check))

    assert [(p.timestamp, p.consumption_kw) for p in points] == [(h3, 100.0), (h2, 200.0)]


def test_history_total_skips_an_hour_where_a_site_is_missing():
    async def check(session):
        return await fetch_history(session, 1, None)

    points, (h3, _) = asyncio.run(with_database(check))

    # h3 : 100 + 50. h2 : SITE991 sans mesure, l'heure est écartée au lieu de creuser la courbe
    assert [(p.timestamp, p.consumption_kw) for p in points] == [(h3, 150.0)]
