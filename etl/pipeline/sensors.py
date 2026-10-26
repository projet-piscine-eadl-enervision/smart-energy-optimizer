"""Pannes de capteur : épisodes de core.sensor_status déduits de /sensors/status.

Un épisode est une ligne (site, capteur, début) dont la fin annoncée est `failing_until`. Les
épisodes en cours sont relus en base à chaque tour, jamais gardés en mémoire : un redémarrage du
collecteur ne crée donc aucun doublon.
"""
from dataclasses import dataclass
from datetime import datetime

from mock_client.schemas.sensor import SiteSensors

SENSORS = frozenset({"consumption", "electrical", "temperature", "humidity", "network"})


@dataclass(frozen=True)
class Episode:
    started_at: datetime
    failing_until: datetime | None


def _row(site_id: str, sensor: str, started_at: datetime, failing_until: datetime | None) -> dict:
    return {"site_id": site_id, "sensor": sensor, "started_at": started_at, "failing_until": failing_until}


def plan_changes(
    statuses: list[SiteSensors], latest: dict[tuple[str, str], Episode], seen_at: datetime
) -> tuple[list[dict], list[dict]]:
    """Renvoie (épisodes à ouvrir, épisodes à mettre à jour) pour ce relevé.

    `latest` : dernier épisode connu de chaque (site, capteur). Un épisode est en cours tant que sa
    fin annoncée n'est pas passée (ou inconnue : il est alors refermé au premier relevé « ok »).
    """
    opened, updated = [], []
    for site in statuses:
        for name, sensor in site.sensors.items():
            if name not in SENSORS:
                continue
            last = latest.get((site.site_id, name))
            in_progress = last is not None and (last.failing_until is None or last.failing_until >= seen_at)
            if sensor.status == "failing":
                if not in_progress:
                    opened.append(_row(site.site_id, name, seen_at, sensor.failing_until))
                elif sensor.failing_until != last.failing_until:
                    updated.append(_row(site.site_id, name, last.started_at, sensor.failing_until))
            elif in_progress and last.failing_until is None:
                updated.append(_row(site.site_id, name, last.started_at, seen_at))
    return opened, updated
