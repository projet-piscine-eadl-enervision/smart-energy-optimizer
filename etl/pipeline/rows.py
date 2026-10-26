"""Lignes prêtes à insérer dans les tables de la base, construites depuis les schémas du mock."""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from mock_client.schemas.alert import Alert
from mock_client.schemas.reading import Reading
from mock_client.schemas.site import Site

Source = Literal["current", "readings"]


def to_decimal(value: float | None) -> Decimal | None:
    """Les colonnes NUMERIC de la base attendent des Decimal, pas des float."""
    return None if value is None else Decimal(str(value))


def site_row(site: Site) -> dict:
    """Ligne de ref.site, depuis un site de GET /sites."""
    return {
        "site_id": site.site_id,
        "site_name": site.site_name,
        "site_type": site.site_type,
        "location": site.location,
        "capacity_kw": to_decimal(site.capacity_kw),
        "status": site.status,
    }


def alert_row(alert: Alert) -> dict:
    """Ligne de core.alert pour une alerte de l'API Mock (origin = 'api')."""
    return {
        "alert_id": alert.alert_id,
        "time": alert.timestamp,
        "site_id": alert.site_id,
        "severity": alert.severity,
        "alert_type": alert.type,
        "message": alert.message,
        "value": to_decimal(alert.value),
        "threshold": to_decimal(alert.threshold),
        "origin": "api",
    }


def energy_reading_row(
    reading: Reading, source: Source, fetched_at: datetime, raw_id: int | None = None
) -> dict:
    """Ligne de core.energy_reading.

    `time` est l'axe de la table (clé primaire, partition, agrégats) :
    - `current` : l'heure de réception, relevée par notre code, car l'horloge du mock a déjà
      changé de fuseau ;
    - `readings` : l'heure de la grille (UTC, fiable), sinon tout le rattrapage serait empilé à
      la date du chargement et fausserait les agrégats et `analytics.site_baseline`.
    `mock_time` garde l'heure du mock telle que reçue.
    """
    if source not in ("current", "readings"):
        raise ValueError(f"unknown source: {source!r}")
    return {
        "time": fetched_at if source == "current" else reading.timestamp,
        "mock_time": reading.timestamp,
        "site_id": reading.site_id,
        "consumption_kw": to_decimal(reading.consumption_kw),
        "voltage_v": to_decimal(reading.voltage_v),
        "current_a": to_decimal(reading.current_a),
        "power_factor": to_decimal(reading.power_factor),
        "temperature_celsius": to_decimal(reading.temperature_celsius),
        "humidity_percent": to_decimal(reading.humidity_percent),
        "null_reasons": reading.null_reasons,
        "data_quality": reading.data_quality,
        "source": source,
        "raw_id": raw_id,
    }
