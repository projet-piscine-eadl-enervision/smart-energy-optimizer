"""Écriture des mesures dans core.energy_reading, commune au collecteur et au rattrapage."""
import psycopg

INSERT_READING = """
INSERT INTO core.energy_reading (time, mock_time, site_id, consumption_kw, voltage_v, current_a,
    power_factor, temperature_celsius, humidity_percent, null_reasons, data_quality, source, raw_id)
VALUES (%(time)s, %(mock_time)s, %(site_id)s, %(consumption_kw)s, %(voltage_v)s, %(current_a)s,
    %(power_factor)s, %(temperature_celsius)s, %(humidity_percent)s, %(null_reasons)s,
    %(data_quality)s, %(source)s, %(raw_id)s)
ON CONFLICT (site_id, time) DO NOTHING
"""


def insert_readings(conn: psycopg.Connection, rows: list[dict]) -> int:
    """Insère les lignes ; une clé (site_id, time) déjà présente est ignorée et n'est pas comptée."""
    if not rows:
        return 0
    with conn.cursor() as cursor:
        cursor.executemany(INSERT_READING, rows)
        return cursor.rowcount
