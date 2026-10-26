"""Traitement : charge les sites du mock dans ref.site.

Usage, depuis etl/ (DATABASE_URL et les variables du mock requises) :
    python -m pipeline load-ref

Les sites déjà présents sont mis à jour : relancer le traitement est sans danger. La réponse du mock
est conservée dans raw.api_response, échec compris, et l'exécution est suivie dans etl.run.
"""
import argparse
import asyncio
import logging

import psycopg

from mock_client.client import RawResponse, fetch_raw
from mock_client.schemas.site import Site
from pipeline import db, runs
from pipeline import raw as raw_store
from pipeline.rows import site_row

logger = logging.getLogger(__name__)

RUN_TYPE = "ref_load"
ENDPOINT = "/sites"

KNOWN_TYPES = "SELECT site_type FROM ref.site_type"
UPSERT_SITE = """
INSERT INTO ref.site (site_id, site_name, site_type, location, capacity_kw, status)
VALUES (%(site_id)s, %(site_name)s, %(site_type)s, %(location)s, %(capacity_kw)s, %(status)s)
ON CONFLICT (site_id) DO UPDATE SET
    site_name = EXCLUDED.site_name,
    site_type = EXCLUDED.site_type,
    location = EXCLUDED.location,
    capacity_kw = EXCLUDED.capacity_kw,
    status = EXCLUDED.status
"""


def parse_sites(raw: RawResponse) -> list[Site]:
    if raw.http_status != 200:
        raise RuntimeError(f"GET {ENDPOINT} answered {raw.http_status}")
    if not isinstance(raw.payload, list) or not raw.payload:
        raise ValueError(f"GET {ENDPOINT} did not return a list of sites")
    return [Site.model_validate(item) for item in raw.payload]


def load_sites(conn: psycopg.Connection, sites: list[Site]) -> int:
    """Insère ou met à jour les sites ; refuse un type absent de ref.site_type (clé étrangère)."""
    known = {row[0] for row in conn.execute(KNOWN_TYPES).fetchall()}
    unknown = sorted({site.site_type for site in sites} - known)
    if unknown:
        raise ValueError(f"site types missing from ref.site_type: {unknown}")
    with conn.transaction(), conn.cursor() as cursor:
        cursor.executemany(UPSERT_SITE, [site_row(site) for site in sites])
    return len(sites)


async def run(conn: psycopg.Connection) -> int:
    run_id = runs.start_run(conn, RUN_TYPE)
    try:
        raw = await fetch_raw(ENDPOINT)
        raw_id = raw_store.save_raw(conn, raw)
        count = load_sites(conn, parse_sites(raw))
        raw_store.mark_processed(conn, [raw_id])
    except Exception as exc:
        runs.finish_run(conn, run_id, error=str(exc))
        raise
    runs.finish_run(conn, run_id, rows_loaded=count)
    return count


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__.split("\n")[0]).parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    with db.connect() as conn:
        count = asyncio.run(run(conn))
    logger.info("%d sites loaded in ref.site", count)
