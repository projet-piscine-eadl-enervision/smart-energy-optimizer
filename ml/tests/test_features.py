import numpy as np
import pandas as pd

from enervision_ml.config import HORIZON_HOURS
from enervision_ml.features import (
    FEATURE_COLUMNS,
    add_features,
    extend_future,
    mask_unreliable_hours,
    to_hourly_grid,
)


def test_lags_reculent_en_heures(hourly):
    df = add_features(to_hourly_grid(hourly))
    row = df[(df["site_id"] == "SITE001") & (df["consumption_kw"] == 300)].iloc[0]
    assert row["lag_24"] == 276
    assert row["lag_168"] == 132


def test_heure_manquante_ne_decale_pas_les_lags(hourly):
    # Sans grille complète, shift(24) reculerait de 24 lignes, soit 25 heures ici
    trou = hourly[~((hourly["site_id"] == "SITE001") & (hourly["consumption_kw"] == 290))]
    df = add_features(to_hourly_grid(trou))
    row = df[(df["site_id"] == "SITE001") & (df["consumption_kw"] == 300)].iloc[0]
    assert row["lag_24"] == 276


def test_lags_ne_melangent_pas_les_sites(hourly):
    df = add_features(to_hourly_grid(hourly))
    first_site2 = df[df["site_id"] == "SITE002"].iloc[0]
    assert pd.isna(first_site2["lag_24"])


def test_aucune_fuite_du_futur(hourly):
    """Modifier les mesures des 24 dernières heures ne doit changer aucune variable de t.

    C'est la garantie qu'en production, à 24 h de l'heure prévue, toutes les variables
    sont déjà connues.
    """
    target = pd.Timestamp("2024-01-12 12:00", tz="UTC")
    altered = hourly.copy()
    recent = (altered["hour"] > target - pd.Timedelta(hours=HORIZON_HOURS)) & (
        altered["hour"] <= target
    )
    altered.loc[recent, "consumption_kw"] = -999.0

    before = add_features(to_hourly_grid(hourly)).set_index(["site_id", "hour"])
    after = add_features(to_hourly_grid(altered)).set_index(["site_id", "hour"])
    pd.testing.assert_frame_equal(
        before.loc[(slice(None), target), FEATURE_COLUMNS],
        after.loc[(slice(None), target), FEATURE_COLUMNS],
    )


def test_calendrier_en_utc_sans_changement_d_heure():
    """Le profil du mock suit l'heure UTC toute l'année (constat 11)."""
    df = pd.DataFrame(
        {
            "hour": pd.to_datetime(["2024-01-15 09:00", "2024-07-15 09:00"], utc=True),
            "site_id": ["SITE001", "SITE001"],
            "site_type": ["office", "office"],
            "capacity_kw": [1.0, 1.0],
            "consumption_kw": [1.0, 1.0],
        }
    )
    features = add_features(df)
    # 9 h UTC reste 9 h en hiver comme en été (en heure de Paris : 10 h puis 11 h)
    assert features["hour_of_day"].tolist() == [9, 9]
    assert features["month"].tolist() == [1, 7]
    assert features["is_weekend"].tolist() == [0, 0]  # deux lundis


def test_heure_trop_incomplete_ecartee():
    df = pd.DataFrame(
        {
            "consumption_kw": [100.0, 140.0, 90.0],
            "nb_readings": [60, 60, 60],
            "nb_missing": [0, 58, 30],
        }
    )
    masked = mask_unreliable_hours(df, max_missing_ratio=0.5)
    # 58 mesures manquantes sur 60 : moyenne sur 2 points, écartée ; 30 sur 60 : gardée
    assert masked["consumption_kw"].isna().tolist() == [False, True, False]
    assert not np.isnan(df["consumption_kw"]).any()  # la donnée d'origine n'est pas modifiée


def test_extend_future_ajoute_l_horizon_par_site(hourly):
    grid = to_hourly_grid(hourly)
    frame = add_features(extend_future(grid))
    future = frame[frame["is_future"]]
    assert len(future) == HORIZON_HOURS * hourly["site_id"].nunique()
    assert future["consumption_kw"].isna().all()
    # Les prévisions s'appuient sur l'historique : lag_24 connu pour toutes les heures futures
    assert future["lag_24"].notna().all()
