"""DÉVELOPPEMENT UNIQUEMENT : charge le CSV du sujet dans la base locale.

Remplace l'ETL tant qu'il ne charge pas l'historique : remplit ref.site et
core.energy_reading, puis rafraîchit analytics.energy_hourly, que lit le ML.
Les tables de l'équipe (ref, core, analytics…) doivent déjà exister.

Le CSV n'est pas le mock (niveaux, noms des sites, anomalies : constat 14) : il sert à faire
tourner le code, pas à évaluer le modèle, qui s'entraîne sur l'historique du mock.

    cp ".../Sujet/data/all_sites_combined.csv" ml/data/
    docker compose run --rm ml python scripts/seed_dev.py
"""

import argparse
import os
import sys

import pandas as pd
import psycopg
from dotenv import load_dotenv

DEFAULT_CSV = "data/all_sites_combined.csv"


def quality(row) -> tuple[str, list[str]]:
    """Qualité et causes des valeurs manquantes, comme les produirait l'ETL."""
    reasons = []
    if pd.isna(row.consumption_kwh):
        reasons.append("consumption_sensor_failure")
    if pd.isna(row.temperature_celsius) or pd.isna(row.humidity_percent):
        reasons.append("weather_sensor_failure")
    if not reasons:
        return "good", reasons
    if pd.isna(row.consumption_kwh):
        return ("critical" if len(reasons) == 2 else "degraded"), reasons
    return "partial", reasons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", nargs="?", default=DEFAULT_CSV)
    args = parser.parse_args()

    load_dotenv()
    if os.getenv("APP_ENV", "dev") != "dev":
        sys.exit("Refusé : ce script ne s'exécute qu'en développement (APP_ENV=dev).")

    df = pd.read_csv(args.csv)
    # Heures lues en UTC, comme l'historique du mock : grille régulière, sans changement
    # d'heure (constat 11)
    df["time"] = pd.to_datetime(df["timestamp"]).dt.tz_localize("UTC")
    df = df.drop_duplicates(subset=["site_id", "time"])
    df[["data_quality", "null_reasons"]] = df.apply(quality, axis=1, result_type="expand")

    # Capacité inconnue du CSV : maximum observé arrondi, suffisant pour du développement
    sites = df.groupby("site_id").agg(
        site_name=("site_name", "first"),
        site_type=("site_type", "first"),
        capacity_kw=("consumption_kwh", "max"),
    )

    with (
        psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as conn,
        conn.cursor() as cur,
    ):
        cur.executemany(
            """INSERT INTO ref.site (site_id, site_name, site_type, capacity_kw)
               VALUES (%s, %s, %s, %s) ON CONFLICT (site_id) DO NOTHING""",
            [(i, r.site_name, r.site_type, round(r.capacity_kw)) for i, r in sites.iterrows()],
        )
        with conn.transaction():
            cur.execute(
                "CREATE TEMP TABLE seed (LIKE core.energy_reading INCLUDING DEFAULTS) "
                "ON COMMIT DROP"
            )
            with cur.copy(
                "COPY seed (time, site_id, consumption_kw, temperature_celsius, "
                "humidity_percent, null_reasons, data_quality, source) FROM STDIN"
            ) as copy:
                for r in df.itertuples(index=False):
                    copy.write_row(
                        (
                            r.time,
                            r.site_id,
                            None if pd.isna(r.consumption_kwh) else r.consumption_kwh,
                            None if pd.isna(r.temperature_celsius) else r.temperature_celsius,
                            None if pd.isna(r.humidity_percent) else r.humidity_percent,
                            r.null_reasons,
                            r.data_quality,
                            "readings",
                        )
                    )
            cur.execute(
                "INSERT INTO core.energy_reading SELECT * FROM seed ON CONFLICT DO NOTHING"
            )
            inserted = cur.rowcount
        # Hors transaction : TimescaleDB l'exige pour rafraîchir un agrégat continu
        cur.execute("CALL refresh_continuous_aggregate('analytics.energy_hourly', NULL, NULL)")

    print(f"{len(sites)} sites, {inserted} mesures insérées ({len(df) - inserted} déjà présentes)")


if __name__ == "__main__":
    main()
