"""Variables d'entrée du modèle.

La consommation du mock est un profil fixe (site, mois, type de jour, heure) multiplié par un
bruit de 5 % sans mémoire (constats 3 à 5) : le calendrier porte toute l'information
prévisible. Les décalages (lag_24, lag_168) ne servent qu'au modèle de comparaison
SeasonalNaive. La température n'est pas utilisée : elle n'explique pas la consommation
(constat 7).

Règle d'or : pour prévoir l'heure t à 24 h, on ne connaît les mesures que jusqu'à t - 24 h.
Toute variable tirée des mesures a donc un décalage d'au moins 24 h (MIN_LAG_HOURS).
"""

import pandas as pd

from enervision_ml.config import CALENDAR_TZ, HORIZON_HOURS, MAX_MISSING_RATIO

MIN_LAG_HOURS = 24
assert HORIZON_HOURS <= MIN_LAG_HOURS, "un décalage plus court que l'horizon utiliserait le futur"

CALENDAR_COLUMNS = ["hour_of_day", "day_of_week", "is_weekend", "month"]
LAG_COLUMNS = ["lag_24", "lag_168"]
FEATURE_COLUMNS = [*CALENDAR_COLUMNS, *LAG_COLUMNS]


def mask_unreliable_hours(df: pd.DataFrame, max_missing_ratio: float = MAX_MISSING_RATIO):
    """Traite comme absente une heure dont trop de mesures n'ont pas de consommation.

    Elle disparaît des notes du modèle et ne sert pas de décalage pour une prévision.
    """
    df = df.copy()
    unreliable = df["nb_missing"] > max_missing_ratio * df["nb_readings"]
    df.loc[unreliable, "consumption_kw"] = float("nan")
    return df


def to_hourly_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par site et par heure, sans trou ; une heure absente devient NaN.

    Indispensable pour que shift(24) recule de 24 heures, et pas de 24 lignes.
    """
    parts = []
    for site_id, site in df.groupby("site_id", sort=True):
        site = site.set_index("hour").sort_index()
        full_range = pd.date_range(site.index.min(), site.index.max(), freq="h")
        site = site.reindex(full_range)
        site.index.name = "hour"
        site["site_id"] = site_id
        site[["site_type", "capacity_kw"]] = site[["site_type", "capacity_kw"]].ffill().bfill()
        parts.append(site.reset_index())
    return pd.concat(parts, ignore_index=True)


def extend_future(grid: pd.DataFrame, horizon: int = HORIZON_HOURS) -> pd.DataFrame:
    """Ajoute, pour chaque site, les heures à prévoir après sa dernière mesure (is_future)."""
    parts = [grid.assign(is_future=False)]
    for site_id, site in grid.groupby("site_id", sort=True):
        last = site["hour"].max()
        future = pd.DataFrame(
            {
                "hour": pd.date_range(last + pd.Timedelta(hours=1), periods=horizon, freq="h"),
                "site_id": site_id,
                "site_type": site["site_type"].iloc[-1],
                "capacity_kw": site["capacity_kw"].iloc[-1],
                "is_future": True,
            }
        )
        parts.append(future)
    return pd.concat(parts, ignore_index=True)


def add_features(grid: pd.DataFrame) -> pd.DataFrame:
    """Calcule FEATURE_COLUMNS sur une grille horaire complète (voir to_hourly_grid)."""
    df = grid.sort_values(["site_id", "hour"]).reset_index(drop=True)
    consumption = df.groupby("site_id")["consumption_kw"]
    df["lag_24"] = consumption.shift(24)
    df["lag_168"] = consumption.shift(168)

    calendar = df["hour"].dt.tz_convert(CALENDAR_TZ)
    df["hour_of_day"] = calendar.dt.hour
    df["day_of_week"] = calendar.dt.dayofweek
    df["is_weekend"] = (calendar.dt.dayofweek >= 5).astype(int)
    df["month"] = calendar.dt.month
    return df
