"""Traitement : collecte en boucle les mesures courantes du mock.

Usage, depuis etl/ (DATABASE_URL et les variables du mock requises) :
    python -m pipeline poll-current [--interval SECONDES] [--once]

À chaque tour (60 s par défaut, ou POLL_INTERVAL_SECONDS) : /current des sites, /sensors/status et
/alerts. Chaque réponse est d'abord enregistrée telle quelle dans raw.api_response, puis transformée
en lignes de core.energy_reading (axe `time` = heure de réception), core.sensor_status et core.alert.
Une erreur sur un appel ou un tour n'arrête pas la boucle ; SIGTERM l'arrête proprement.
"""
import argparse
import asyncio
import logging
import signal
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx2
import psycopg
from pydantic import ValidationError

from mock_client.client import fetch_raw
from mock_client.schemas.reading import Reading
from mock_client.services.alert_service import parse_alerts
from mock_client.services.sensor_service import parse_sensors_status
from pipeline import db, heartbeat, raw, runs
from pipeline.jobs import load_ref
from pipeline.readings import insert_readings
from pipeline.rows import alert_row, energy_reading_row
from pipeline.sensors import Episode, plan_changes

logger = logging.getLogger(__name__)

RUN_TYPE = "poll_current"
SENSORS_PATH = "/sensors/status"
ALERTS_PATH = "/alerts"
SUMMARY_EVERY_TOURS = 10  # une ligne etl.run toutes les 10 tours, et une à chaque série d'échecs
SKEW_WARNING = timedelta(minutes=5)  # écart toléré entre l'heure du mock et notre heure de réception

ALERT_TYPES = "SELECT alert_type FROM ref.alert_type"
SEVERITIES = "SELECT severity FROM ref.severity"
LATEST_EPISODES = (
    "SELECT DISTINCT ON (site_id, sensor) site_id, sensor, started_at, failing_until"
    " FROM core.sensor_status ORDER BY site_id, sensor, started_at DESC"
)
INSERT_EPISODE = (
    "INSERT INTO core.sensor_status (site_id, sensor, started_at, failing_until)"
    " VALUES (%(site_id)s, %(sensor)s, %(started_at)s, %(failing_until)s)"
    " ON CONFLICT (site_id, sensor, started_at) DO NOTHING"
)
UPDATE_EPISODE = (
    "UPDATE core.sensor_status SET failing_until = %(failing_until)s"
    " WHERE site_id = %(site_id)s AND sensor = %(sensor)s AND started_at = %(started_at)s"
)
INSERT_ALERT = """
INSERT INTO core.alert (alert_id, time, site_id, severity, alert_type, message, value, threshold, origin)
VALUES (%(alert_id)s, %(time)s, %(site_id)s, %(severity)s, %(alert_type)s, %(message)s, %(value)s,
    %(threshold)s, %(origin)s)
ON CONFLICT (alert_id) DO NOTHING
"""


@dataclass
class Known:
    """Ce que la base accepte : les clés étrangères que les réponses du mock doivent respecter."""

    sites: list[str]
    alert_types: set[str]
    severities: set[str]


@dataclass
class Tour:
    loaded: int = 0  # lignes de core.energy_reading
    rejected: int = 0  # réponses ou lignes écartées
    alerts: int = 0
    sensor_changes: int = 0
    max_skew: timedelta = timedelta(0)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.loaded > 0

    def reject(self, path: str, reason: str) -> None:
        self.rejected += 1
        self.errors.append(f"{path}: {reason}")
        logger.warning("%s rejected: %s", path, reason)


@dataclass
class Summary:
    tours: int = 0
    loaded: int = 0
    rejected: int = 0
    period_start: datetime | None = None
    failures_in_row: int = 0


async def ensure_sites(conn: psycopg.Connection) -> Known:
    """Lit les sites en base ; si ref.site est vide, la charge d'abord depuis le mock."""
    return Known(
        await load_ref.ensure_site_ids(conn),
        {row[0] for row in conn.execute(ALERT_TYPES).fetchall()},
        {row[0] for row in conn.execute(SEVERITIES).fetchall()},
    )


def reading_rows(parsed: list[tuple[int, datetime, Reading]], tour: Tour) -> list[dict]:
    rows = []
    for raw_id, fetched_at, reading in parsed:
        skew = abs(fetched_at - reading.timestamp)
        tour.max_skew = max(tour.max_skew, skew)
        if skew > SKEW_WARNING:
            logger.warning("%s: mock clock differs by %s from ours", reading.site_id, skew)
        rows.append(energy_reading_row(reading, "current", fetched_at, raw_id))
    return rows


def write_alerts(conn: psycopg.Connection, alerts, known: Known, tour: Tour) -> None:
    rows = []
    for alert in alerts:
        if (
            alert.site_id in known.sites
            and alert.type in known.alert_types
            and alert.severity in known.severities
        ):
            rows.append(alert_row(alert))
        else:
            tour.reject(ALERTS_PATH, f"{alert.alert_id}: unknown site, type or severity")
    if rows:
        with conn.cursor() as cursor:
            cursor.executemany(INSERT_ALERT, rows)
    tour.alerts = len(rows)


def write_sensors(conn: psycopg.Connection, statuses, seen_at: datetime, known: Known, tour: Tour) -> None:
    statuses = [status for status in statuses if status.site_id in known.sites]
    latest = {
        (site_id, sensor): Episode(started_at, failing_until)
        for site_id, sensor, started_at, failing_until in conn.execute(LATEST_EPISODES).fetchall()
    }
    opened, updated = plan_changes(statuses, latest, seen_at)
    with conn.cursor() as cursor:
        if opened:
            cursor.executemany(INSERT_EPISODE, opened)
        if updated:
            cursor.executemany(UPDATE_EPISODE, updated)
    tour.sensor_changes = len(opened) + len(updated)


async def tour(conn: psycopg.Connection, known: Known) -> Tour:
    """Un tour : appelle le mock, enregistre le brut, puis écrit les lignes dans une transaction."""
    result = Tour()
    paths = [f"/sites/{site_id}/current" for site_id in known.sites] + [SENSORS_PATH, ALERTS_PATH]
    answers = await asyncio.gather(*(fetch_raw(path) for path in paths), return_exceptions=True)

    readings, statuses, alerts, processed = [], None, None, []
    sensors_seen_at = None
    for path, answer in zip(paths, answers, strict=True):
        if isinstance(answer, httpx2.RequestError):
            result.reject(path, repr(answer))
            continue
        if isinstance(answer, BaseException):
            raise answer
        raw_id = raw.save_raw(conn, answer)
        if answer.http_status != 200:
            result.reject(path, f"HTTP {answer.http_status}")
            continue
        try:
            if path == SENSORS_PATH:
                statuses, sensors_seen_at = parse_sensors_status(answer.payload), answer.fetched_at
            elif path == ALERTS_PATH:
                alerts = parse_alerts(answer.payload)
            else:
                readings.append((raw_id, answer.fetched_at, Reading.model_validate(answer.payload)))
        except (ValidationError, TypeError, AttributeError) as exc:
            result.reject(path, f"unexpected payload ({type(exc).__name__})")
            continue
        processed.append(raw_id)

    rows = reading_rows(readings, result)
    with conn.transaction():
        result.loaded = insert_readings(conn, rows)
        if statuses is not None:
            write_sensors(conn, statuses, sensors_seen_at, known, result)
        if alerts is not None:
            write_alerts(conn, alerts, known, result)
        raw.mark_processed(conn, processed)
    logger.info(
        "tour: %d readings, %d rejected, %d alerts, %d sensor changes, max clock gap %.0fs",
        result.loaded, result.rejected, result.alerts, result.sensor_changes, result.max_skew.total_seconds(),
    )
    return result


def write_run(conn: psycopg.Connection, summary: Summary, now: datetime, error: str | None = None) -> None:
    run_id = runs.start_run(conn, RUN_TYPE, summary.period_start, now)
    runs.finish_run(conn, run_id, summary.loaded, summary.rejected, error)


def account(conn: psycopg.Connection, summary: Summary, result: Tour) -> None:
    """Tient le compte dans etl.run : un résumé périodique, et une ligne par série d'échecs."""
    now = datetime.now(UTC)
    summary.period_start = summary.period_start or now
    summary.tours += 1
    summary.loaded += result.loaded
    summary.rejected += result.rejected
    if result.ok:
        summary.failures_in_row = 0
    else:
        summary.failures_in_row += 1
        if summary.failures_in_row == 1 or summary.failures_in_row % SUMMARY_EVERY_TOURS == 0:
            write_run(conn, summary, now, error="; ".join(result.errors)[:500] or "no reading loaded")
    if summary.tours >= SUMMARY_EVERY_TOURS:
        write_run(conn, summary, now)
        summary.tours = summary.loaded = summary.rejected = 0
        summary.period_start = None


async def run_forever(connect, interval: float, stop: asyncio.Event, once: bool = False) -> None:
    conn, known, summary = None, None, Summary()
    try:
        while True:
            started = time.monotonic()
            try:
                if conn is None or conn.closed:
                    conn = connect()
                    known = await ensure_sites(conn)
                result = await tour(conn, known)
            except Exception as exc:
                logger.exception("tour failed")
                result = Tour(errors=[repr(exc)])
                if isinstance(exc, psycopg.OperationalError) and conn is not None:
                    conn.close()
                    conn = None
            if result.ok:
                heartbeat.beat()
            if conn is not None:
                try:
                    account(conn, summary, result)
                except psycopg.Error:
                    logger.exception("etl.run not written")
            if once or stop.is_set():
                return
            try:
                await asyncio.wait_for(stop.wait(), max(0.0, interval - (time.monotonic() - started)))
                return
            except TimeoutError:
                pass
    finally:
        if conn is not None:
            conn.close()


async def serve(interval: float, once: bool) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(signum, stop.set)
        except NotImplementedError:  # Windows : Ctrl+C interrompt la boucle
            pass
    await run_forever(db.connect, interval, stop, once)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--interval", type=float, default=heartbeat.interval_seconds(), help="seconds between two tours")
    parser.add_argument("--once", action="store_true", help="run a single tour, for a trial")
    args = parser.parse_args(argv)
    if args.interval <= 0:
        parser.error("--interval must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    asyncio.run(serve(args.interval, args.once))
