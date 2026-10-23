import numpy as np
import pandas as pd
import pytest


def make_hourly(hours: int = 400, sites: tuple[str, ...] = ("SITE001", "SITE002")) -> pd.DataFrame:
    """Données horaires factices au format de data.load_hourly ; consommation = n° de l'heure."""
    frames = []
    start = pd.Timestamp("2024-01-01", tz="UTC")
    for offset, site_id in enumerate(sites):
        frames.append(
            pd.DataFrame(
                {
                    "hour": pd.date_range(start, periods=hours, freq="h"),
                    "site_id": site_id,
                    "site_type": "office",
                    "capacity_kw": 1000.0,
                    "consumption_kw": np.arange(hours, dtype=float) + 1000 * offset,
                    "temperature_celsius": 10.0,
                    "nb_readings": 60,
                    "nb_missing": 0,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def make_mock_like(days: int, seed: int = 0) -> pd.DataFrame:
    """Données qui se comportent comme le mock (docs/analyse-api-mock.md, constats 3 à 5).

    Profil fixe (jour ouvré de 8 h à 19 h, week-end plat, facteur du mois) multiplié par un
    bruit gaussien de 5 % sans mémoire.
    """
    rng = np.random.default_rng(seed)
    df = make_hourly(hours=24 * days)
    hour = df["hour"].dt.hour
    weekend = df["hour"].dt.dayofweek >= 5
    month_factor = 1 - 0.06 * np.cos(2 * np.pi * (df["hour"].dt.month - 4) / 6)
    base = np.where(weekend, 70.0, np.where((hour >= 8) & (hour < 19), 165.0, 62.0))
    level = np.where(df["site_id"] == "SITE001", 1.0, 0.9)
    df["consumption_kw"] = base * month_factor * level * (1 + 0.05 * rng.standard_normal(len(df)))
    return df


@pytest.fixture
def hourly() -> pd.DataFrame:
    return make_hourly()
