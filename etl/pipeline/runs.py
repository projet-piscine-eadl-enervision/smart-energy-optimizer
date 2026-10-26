"""Suivi des exécutions dans etl.run : une ligne par traitement, ouverte puis refermée."""
from datetime import datetime

import psycopg


def start_run(
    conn: psycopg.Connection,
    run_type: str,
    period_start: datetime | None = None,
    period_end: datetime | None = None,
) -> int:
    with conn.transaction():
        row = conn.execute(
            "INSERT INTO etl.run (run_type, period_start, period_end) VALUES (%s, %s, %s) RETURNING run_id",
            (run_type, period_start, period_end),
        ).fetchone()
    return row[0]


def finish_run(
    conn: psycopg.Connection, run_id: int, rows_loaded: int = 0, rows_rejected: int = 0, error: str | None = None
) -> None:
    with conn.transaction():
        conn.execute(
            "UPDATE etl.run SET finished_at = now(), status = %s, rows_loaded = %s, rows_rejected = %s,"
            " error_message = %s WHERE run_id = %s",
            ("failed" if error else "success", rows_loaded, rows_rejected, error, run_id),
        )
