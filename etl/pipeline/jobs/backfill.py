"""Traitement : rattrape l'historique du mock par pas d'une heure.

Usage, depuis etl/ (DATABASE_URL et les variables du mock requises) :
    python -m pipeline backfill [--start 2023-01-01] [--end AAAA-MM-JJ[THH]] [--site SITE001]

Le mock renvoie `limit` points répartis sur la fenêtre (début inclus, fin exclue) : une fenêtre de N
heures avec limit=N donne exactement un point par heure pleine. Début et fin sont ramenés à l'heure
pleine, donc relancer le traitement redemande les mêmes instants ; une ligne déjà présente
(site, heure) est conservée telle quelle. Le mock redessine un bruit à chaque appel : le premier
passage fait foi.

Après le chargement, l'agrégat horaire est rafraîchi sur la période (sa politique automatique ne
couvre que les trois derniers jours) et analytics.site_baseline est recalculée. Ces deux opérations
demandent d'être propriétaire des vues : la connexion se fait avec le compte propriétaire.
"""
import argparse
import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx2
import psycopg
from pydantic import ValidationError

from mock_client.client import fetch_raw
from mock_client.schemas.reading import Reading
from pipeline import db, raw, runs
from pipeline.jobs import load_ref
from pipeline.readings import insert_readings
from pipeline.rows import energy_reading_row

logger = logging.getLogger(__name__)

RUN_TYPE = "backfill"
DEFAULT_START = datetime(2023, 1, 1, tzinfo=UTC)
WINDOW_HOURS = 1000  # limite du mock par appel
END_MARGIN = timedelta(minutes=5)  # la fin ne doit pas dépasser l'horloge du mock (400 sinon)
HOUR = timedelta(hours=1)


def floor_hour(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def windows(start: datetime, end: datetime):
    """Fenêtres (début, nombre d'heures) de 1000 heures au plus, de start inclus à end exclu."""
    cursor = start
    while cursor < end:
        hours = min(WINDOW_HOURS, (end - cursor) // HOUR)
        yield cursor, hours
        cursor += hours * HOUR


async def backfill_site(conn: psycopg.Connection, site_id: str, start: datetime, end: datetime) -> tuple[int, list[str]]:
    """Charge un site sur [start, end) ; renvoie (lignes insérées, erreurs). Une ligne etl.run par site."""
    run_id = runs.start_run(conn, RUN_TYPE, start, end)
    loaded, rejected, errors = 0, 0, []
    for window_start, hours in windows(start, end):
        window_end = window_start + hours * HOUR
        params = {
            "site_id": site_id,
            "start_time": window_start.isoformat(),
            "end_time": window_end.isoformat(),
            "limit": hours,
        }
        try:
            answer = await fetch_raw("/readings", params)
        except httpx2.RequestError as exc:
            errors.append(f"{window_start:%Y-%m-%d}: {exc!r}")
            rejected += hours
            continue
        raw_id = raw.save_raw(conn, answer)
        try:
            if answer.http_status != 200:
                raise ValueError(f"HTTP {answer.http_status}")
            readings = [Reading.model_validate(item) for item in answer.payload]
        except (ValueError, ValidationError, TypeError) as exc:
            errors.append(f"{window_start:%Y-%m-%d}: {exc}")
            rejected += hours
            continue
        if len(readings) != hours:
            logger.warning("%s %s: %d points received, %d expected", site_id, window_start, len(readings), hours)
        rows = [energy_reading_row(reading, "readings", answer.fetched_at, raw_id) for reading in readings]
        with conn.transaction():
            loaded += insert_readings(conn, rows)
            raw.mark_processed(conn, [raw_id])
    runs.finish_run(conn, run_id, loaded, rejected, "; ".join(errors)[:500] or None)
    logger.info("%s: %d rows inserted, %d points rejected", site_id, loaded, rejected)
    return loaded, errors


def refresh(conn: psycopg.Connection, start: datetime, end: datetime) -> None:
    """Hors transaction (connexion en autocommit) : le rafraîchissement d'un agrégat l'exige."""
    conn.execute("CALL refresh_continuous_aggregate('analytics.energy_hourly', %s::timestamptz, %s::timestamptz)", (start, end))
    conn.execute("SELECT analytics.refresh_site_baseline()")


async def run(conn: psycopg.Connection, start: datetime, end: datetime, only_site: str | None = None) -> int:
    site_ids = await load_ref.ensure_site_ids(conn)
    if only_site:
        if only_site not in site_ids:
            raise ValueError(f"unknown site {only_site!r}, known: {site_ids}")
        site_ids = [only_site]
    total, errors = 0, []
    for site_id in site_ids:
        loaded, site_errors = await backfill_site(conn, site_id, start, end)
        total += loaded
        errors += [f"{site_id} {error}" for error in site_errors]
    refresh(conn, start, end)
    if errors:
        raise RuntimeError(f"{len(errors)} windows failed, first: {errors[0]}")
    return total


def parse_moment(value: str) -> datetime:
    return floor_hour(datetime.fromisoformat(value))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start", type=parse_moment, default=DEFAULT_START, help="first hour, UTC (default 2023-01-01)")
    parser.add_argument("--end", type=parse_moment, help="end, excluded, UTC (default: now, rounded down to the hour)")
    parser.add_argument("--site", help="a single site, for example SITE001")
    args = parser.parse_args(argv)
    end = args.end or floor_hour(datetime.now(UTC) - END_MARGIN)
    if args.start >= end:
        parser.error("--start must be before --end")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    with db.connect() as conn:
        total = asyncio.run(run(conn, args.start, end, args.site))
    logger.info("%d rows inserted between %s and %s", total, args.start, end)
