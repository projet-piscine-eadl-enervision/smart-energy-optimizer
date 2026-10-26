"""Réponses brutes du mock dans raw.api_response : enregistrées d'abord, marquées traitées ensuite."""
import psycopg
from psycopg.types.json import Jsonb

from mock_client.client import RawResponse

INSERT_RAW = (
    "INSERT INTO raw.api_response (endpoint, params, http_status, fetched_at, payload)"
    " VALUES (%s, %s, %s, %s, %s) RETURNING id"
)
MARK_PROCESSED = "UPDATE raw.api_response SET processed_at = now() WHERE id = ANY(%s)"


def save_raw(conn: psycopg.Connection, raw: RawResponse) -> int:
    """Enregistre la réponse telle que reçue, échec compris, dans sa propre transaction.

    Elle reste en base même si le traitement qui suit échoue.
    """
    with conn.transaction():
        row = conn.execute(
            INSERT_RAW,
            (raw.endpoint, Jsonb(raw.params), raw.http_status, raw.fetched_at, Jsonb(raw.payload)),
        ).fetchone()
    return row[0]


def mark_processed(conn: psycopg.Connection, raw_ids: list[int]) -> None:
    if raw_ids:
        with conn.transaction():
            conn.execute(MARK_PROCESSED, (raw_ids,))
