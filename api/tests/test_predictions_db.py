"""Requêtes de /predictions contre TimescaleDB migrée.

Ignorés sans base : conftest met une adresse de test qui ne répond pas. En CI, le job python
démarre la base, applique les migrations et fournit DATABASE_URL. Les sites SITE990 et SITE991
et les versions de modèle api-test-1 et api-test-2 sont créés puis supprimés par le test.
"""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.routes.predictions import PEAKS_SQL, fetch_predictions
from app.core.config import settings

pytestmark = pytest.mark.skipif(
    settings.DATABASE_URL.endswith("@localhost:5432/test"),
    reason="DATABASE_URL de test : pas de base",
)

SITES = ("SITE990", "SITE991")
OLD, NEW = "api-test-1", "api-test-2"
INSERT = text(
    "INSERT INTO ml.prediction (target_time, site_id, model_version, predicted_kw, is_peak, predicted_at) "
    "VALUES (:t, :site, :version, :kw, :peak, :at)"
)


async def clean(conn):
    await conn.execute(text("DELETE FROM ml.prediction WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})
    await conn.execute(text("DELETE FROM ml.model_run WHERE model_version = ANY(:versions)"), {"versions": [OLD, NEW]})
    await conn.execute(text("DELETE FROM ref.site WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})


async def with_database(check):
    """Prépare les prévisions de test, exécute check(session), puis nettoie."""
    engine = create_async_engine(settings.DATABASE_URL)
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    older, newer = now - timedelta(hours=1), now
    rows = [
        # La version 2 est écrite plus tard : elle remplace la version 1 pour la même heure,
        # y compris son drapeau de pic
        (hour + timedelta(hours=1), "SITE990", OLD, 10, True, older),
        (hour + timedelta(hours=1), "SITE990", NEW, 12, False, newer),
        (hour + timedelta(hours=1), "SITE991", NEW, 20, True, newer),
        (hour + timedelta(hours=2), "SITE990", NEW, 11, False, newer),
        (hour + timedelta(hours=2), "SITE991", NEW, 21, False, newer),
        # Hors fenêtre : une heure passée et une heure au-delà de l'horizon de 24 h
        (hour - timedelta(hours=2), "SITE990", NEW, 99, True, newer),
        (hour + timedelta(hours=30), "SITE990", NEW, 50, True, newer),
    ]
    async with engine.begin() as conn:
        await clean(conn)
        for site in SITES:
            await conn.execute(
                text("INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) VALUES (:s, 'Site de test', 'office', 500)"),
                {"s": site},
            )
        for version in (OLD, NEW):
            await conn.execute(
                text(
                    "INSERT INTO ml.model_run (model_version, run_id, model, train_start, train_end, data_end, "
                    "promoted, decision, shiftable_ratio, peak_penalty_eur_kwh) "
                    "VALUES (:v, 'run-test', 'site_profile', :t, :t, :t, false, 'test', 0.1, 0.15)"
                ),
                {"v": version, "t": older},
            )
        await conn.execute(
            text("INSERT INTO ml.peak_threshold (model_version, site_id, threshold_kw) VALUES (:v, :s, :k)"),
            [{"v": NEW, "s": "SITE990", "k": 11}, {"v": NEW, "s": "SITE991", "k": 18}],
        )
        for t, site, version, kw, peak, at in rows:
            await conn.execute(INSERT, {"t": t, "site": site, "version": version, "kw": kw, "peak": peak, "at": at})
    try:
        async with AsyncSession(engine) as session:
            return await check(session)
    finally:
        async with engine.begin() as conn:
            await clean(conn)
        await engine.dispose()


def test_latest_prediction_wins_for_one_site():
    async def check(session):
        return await fetch_predictions(session, 24, "SITE990")

    result = asyncio.run(with_database(check))

    assert [p.predicted_kw for p in result] == [12.0, 11.0]
    assert {p.model_version for p in result} == {NEW}
    assert {p.site_id for p in result} == {"SITE990"}
    assert [p.is_peak for p in result] == [False, False]


def test_total_sums_sites_and_has_no_peak_flag():
    async def check(session):
        rows = await fetch_predictions(session, 24, None)
        return [p for p in rows if p.model_version == NEW and p.predicted_kw == 32.0]

    result = asyncio.run(with_database(check))

    # Heures +1 et +2 : 12 + 20 et 11 + 21, soit 32 kW chacune ; le seuil de pic est propre à chaque site
    assert [p.predicted_kw for p in result] == [32.0, 32.0]
    assert [p.is_peak for p in result] == [None, None]
    assert {p.site_id for p in result} == {"ALL"}


def test_one_site_keeps_its_peak_flag():
    async def check(session):
        return await fetch_predictions(session, 24, "SITE991")

    result = asyncio.run(with_database(check))

    assert [p.predicted_kw for p in result] == [20.0, 21.0]
    assert [p.is_peak for p in result] == [True, False]


def test_horizon_limits_the_window():
    async def check(session):
        return await fetch_predictions(session, 1, "SITE990")

    # Horizon d'une heure : seule l'heure en cours est incluse, et aucune prévision n'est écrite pour elle
    assert asyncio.run(with_database(check)) == []


def test_peaks_use_the_latest_flag_and_the_site_threshold():
    async def check(session):
        rows = (await session.execute(PEAKS_SQL, {"hours": 24, "site_id": None})).all()
        return [(r.site_id, float(r.predicted_kw), float(r.threshold_kw), r.model_version) for r in rows]

    result = asyncio.run(with_database(check))

    # Seule SITE991 est en pic : le pic ancien de SITE990 (version 1) est annulé par la version 2, et les pics
    # hors fenêtre sont ignorés
    assert result == [("SITE991", 20.0, 18.0, NEW)]


def test_peaks_can_be_limited_to_a_site():
    async def check(session):
        rows = (await session.execute(PEAKS_SQL, {"hours": 24, "site_id": "SITE990"})).all()
        return list(rows)

    assert asyncio.run(with_database(check)) == []
