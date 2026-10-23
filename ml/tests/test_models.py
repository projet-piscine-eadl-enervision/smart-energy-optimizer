import numpy as np
import pandas as pd
import pytest

from enervision_ml.evaluate import evaluate, temporal_split
from enervision_ml.features import add_features, to_hourly_grid
from enervision_ml.models import (
    ConsumptionModel,
    SeasonalNaive,
    SiteProfile,
    peak_thresholds,
)
from tests.conftest import make_mock_like


def profile_frame(**columns) -> pd.DataFrame:
    base = {"site_id": "A", "month": 1, "is_weekend": 0, "hour_of_day": 10}
    n = len(next(iter(columns.values())))
    return pd.DataFrame({**{k: [v] * n for k, v in base.items()}, **columns})


def test_site_profile_predit_la_moyenne_de_la_case():
    train = profile_frame(consumption_kw=[100.0, 110.0, np.nan], hour_of_day=[10, 10, 10])
    model = SiteProfile().fit(train)
    assert model.predict(profile_frame(hour_of_day=[10])).tolist() == [105.0]


def test_site_profile_mois_jamais_vu_prend_la_moyenne_sans_le_mois():
    train = profile_frame(consumption_kw=[100.0, 120.0], month=[1, 2])
    model = SiteProfile().fit(train)
    assert model.predict(profile_frame(month=[7])).tolist() == [110.0]


def test_seasonal_naive_prend_la_semaine_derniere_sinon_la_veille():
    features = pd.DataFrame({"lag_168": [10.0, np.nan], "lag_24": [99.0, 20.0]})
    assert SeasonalNaive().predict(features).tolist() == [10.0, 20.0]


def test_profil_bat_le_naif_sur_des_donnees_comme_le_mock():
    """Le naïf recopie le bruit de la semaine passée : environ 1,4 fois l'erreur du profil.

    C'est la justification du choix de SiteProfile comme référence (constat 3).
    """
    data = add_features(to_hourly_grid(make_mock_like(days=500)))
    train, validation, _ = temporal_split(data)
    thresholds = peak_thresholds(train)
    profile = evaluate(validation, SiteProfile().fit(train).predict(validation), thresholds)
    naive = evaluate(validation, SeasonalNaive().predict(validation), thresholds)

    assert profile["nmae"] == pytest.approx(0.05 * np.sqrt(2 / np.pi), rel=0.15)  # plancher du bruit
    # Attendu : √2 ≈ 1,4 fois (deux bruits indépendants au lieu d'un), marge pour le hasard
    assert naive["nmae"] > 1.2 * profile["nmae"]


def test_seuil_de_pic_relatif_a_la_moyenne_du_site():
    train = pd.DataFrame(
        {"site_id": ["bureau"] * 2 + ["datacenter"] * 2, "consumption_kw": [60, 140, 740, 760]}
    )
    thresholds = peak_thresholds(train, ratio=1.25)
    assert thresholds == {"bureau": 125.0, "datacenter": 937.5}


def test_site_plat_n_a_pas_de_pic_de_demande():
    data = add_features(to_hourly_grid(make_mock_like(days=30)))
    # Datacenter : consommation plate autour de 735 kW avec 5 % de bruit
    flat = data.assign(consumption_kw=735 * (1 + 0.05 * np.random.default_rng(1).standard_normal(len(data))))
    thresholds = peak_thresholds(flat)
    assert not (flat["consumption_kw"] > flat["site_id"].map(thresholds)).any()


def test_consumption_model_signale_les_pics():
    model = ConsumptionModel(SeasonalNaive(), {"A": 50.0, "B": 500.0})
    model_input = pd.DataFrame(
        {"site_id": ["A", "B"], "lag_168": [80.0, 80.0], "lag_24": [np.nan, np.nan]}
    )
    output = model.predict(None, model_input)
    assert output["predicted_kw"].tolist() == [80.0, 80.0]
    assert output["is_peak"].tolist() == [True, False]
