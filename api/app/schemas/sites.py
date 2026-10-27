from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Period = Literal["hour", "day", "week", "month"]


class Site(BaseModel):
    """Site avec sa dernière consommation connue (non nulle) et la qualité du dernier relevé."""

    site_id: str
    site_name: str
    site_type: str
    location: str | None
    capacity_kw: float
    status: str
    last_consumption_kw: float | None
    last_reading_age_minutes: float | None
    last_quality: str | None


class SiteConsumptionPoint(BaseModel):
    """Consommation d'une période : énergie (kWh) et pointe (kW)."""

    timestamp: datetime
    energy_kwh: float
    max_kw: float | None


class SiteQuality(BaseModel):
    """Qualité des relevés d'un site sur les `days` derniers jours.

    missing_ratio : part des relevés sans consommation. by_quality : nombre de relevés par niveau
    (good, partial, degraded, critical). sensor_outages : pannes de capteur commencées sur la période.
    """

    site_id: str
    days: int
    readings: int
    missing_ratio: float | None
    by_quality: dict[str, int]
    sensor_outages: int
