"""Requête de /recommendations contre TimescaleDB migrée, après app.refresh_recommendations().

Ignorés sans base (adresse de test de conftest). Les sites SITE990 et SITE991 (bureaux), la version de
modèle api-rec-test, une alerte et leurs conseils sont créés puis supprimés par le test.
"""
import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.api.routes.recommendations import fetch_recommendations
from app.core.config import settings

pytestmark = pytest.mark.skipif(
    settings.DATABASE_URL.endswith("@localhost:5432/test"),
    reason="DATABASE_URL de test : pas de base",
)

SITES = ("SITE990", "SITE991")
VERSION = "api-rec-test"


async def clean(conn):
    await conn.execute(text("DELETE FROM app.recommendation WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})
    await conn.execute(text("DELETE FROM core.alert WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})
    await conn.execute(text("DELETE FROM ml.prediction WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})
    await conn.execute(text("DELETE FROM ml.model_run WHERE model_version = :v"), {"v": VERSION})
    await conn.execute(text("DELETE FROM ref.site WHERE site_id = ANY(:sites)"), {"sites": list(SITES)})


async def with_database(check):
    engine = create_async_engine(settings.DATABASE_URL)
    now = datetime.now(UTC)
    hour = now.replace(minute=0, second=0, microsecond=0)
    async with engine.begin() as conn:
        await clean(conn)
        for site in SITES:
            await conn.execute(
                text("INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw) VALUES (:s, 'Site de test', 'office', 500)"),
                {"s": site},
            )
        await conn.execute(
            text(
                "INSERT INTO ml.model_run (model_version, run_id, model, train_start, train_end, data_end, "
                "promoted, decision, shiftable_ratio, peak_penalty_eur_kwh) "
                "VALUES (:v, 'run-test', 'site_profile', :t, :t, :t, false, 'test', 0.1, 0.15)"
            ),
            {"v": VERSION, "t": now},
        )
        await conn.execute(
            text("INSERT INTO ml.peak_threshold (model_version, site_id, threshold_kw) VALUES (:v, :s, :k)"),
            [{"v": VERSION, "s": "SITE990", "k": 120}, {"v": VERSION, "s": "SITE991", "k": 100}],
        )
        # SITE990 : dépassement de 10 kW, sous la part décalable (13 kW). SITE991 : dépassement de 100 kW,
        # la part décalable (20 kW) borne l'économie
        for site, kw in (("SITE990", 130), ("SITE991", 200)):
            await conn.execute(
                text(
                    "INSERT INTO ml.prediction (target_time, site_id, model_version, predicted_kw, is_peak) "
                    "VALUES (:t, :s, :v, :kw, true)"
                ),
                {"t": hour + timedelta(hours=1), "s": site, "v": VERSION, "kw": kw},
            )
        await conn.execute(
            text(
                "INSERT INTO core.alert (alert_id, time, site_id, severity, alert_type, origin) "
                "VALUES ('api-rec-test-1', :t, 'SITE990', 'high', 'sensor', 'api')"
            ),
            {"t": now - timedelta(hours=2)},
        )
        await conn.execute(text("SELECT app.refresh_recommendations()"))
    try:
        async with AsyncSession(engine) as session:
            return await check(session)
    finally:
        async with engine.begin() as conn:
            await clean(conn)
        await engine.dispose()


def test_recommendations_for_a_predicted_peak_carry_a_bounded_saving():
    async def check(session):
        return await fetch_recommendations(session, 24, None, 50)

    result = asyncio.run(with_database(check))

    peaks = {r.site_id: r for r in result if r.alert_type == "threshold" and r.site_id in SITES}
    assert peaks["SITE990"].estimated_saving_kw == pytest.approx(10.0)
    assert peaks["SITE991"].estimated_saving_kw == pytest.approx(20.0)
    assert peaks["SITE990"].title == "Dépassement du seuil : Site de test"


def test_recommendations_for_an_alert_have_no_saving():
    async def check(session):
        return await fetch_recommendations(session, 24, "SITE990", 50)

    result = asyncio.run(with_database(check))

    sensor = [r for r in result if r.alert_type == "sensor"]
    assert len(sensor) == 2  # deux conseils génériques pour un capteur défaillant
    assert all(r.estimated_saving_kw is None for r in sensor)
    assert {r.site_id for r in result} == {"SITE990"}


def test_limit_caps_the_list():
    async def check(session):
        return await fetch_recommendations(session, 24, None, 1)

    assert len(asyncio.run(with_database(check))) == 1
