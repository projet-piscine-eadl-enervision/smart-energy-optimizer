import numpy as np
import pandas as pd
import pytest

from enervision_ml.evaluate import evaluate, temporal_split
from enervision_ml.features import add_features, to_hourly_grid
from enervision_ml.models import (
    ConsumptionModel,
    GradientBoosting,
    SeasonalNaive,
    SiteProfile,
    peak_thresholds,
)
from tests.conftest import make_mock_like


def profile_frame(**columns) -> pd.DataFrame:
    base = {"site_id": "A", "month": 1, "is_weekend": 0, "hour_of_day": 10}
    n = len(next(iter(columns.values())))
    return pd.DataFrame({**{k: [v] * n for k, v in base.items()}, **columns})


def test_site_profile_predicts_cell_mean():
    train = profile_frame(consumption_kw=[100.0, 110.0, np.nan], hour_of_day=[10, 10, 10])
    model = SiteProfile().fit(train)
    assert model.predict(profile_frame(hour_of_day=[10])).tolist() == [105.0]


def test_site_profile_unseen_month_falls_back_to_mean_without_month():
    train = profile_frame(consumption_kw=[100.0, 120.0], month=[1, 2])
    model = SiteProfile().fit(train)
    assert model.predict(profile_frame(month=[7])).tolist() == [110.0]


def test_seasonal_naive_uses_last_week_else_yesterday():
    features = pd.DataFrame({"lag_168": [10.0, np.nan], "lag_24": [99.0, 20.0]})
    assert SeasonalNaive().predict(features).tolist() == [10.0, 20.0]


def test_profile_beats_naive_on_mock_like_data():
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


def test_gradient_boosting_matches_profile_on_mock_like_data():
    """Le calendrier porte tout le prévisible : le boosting rejoint le profil, sans pouvoir
    faire beaucoup mieux, et bat le naïf."""
    data = add_features(to_hourly_grid(make_mock_like(days=500)))
    train, validation, _ = temporal_split(data)
    thresholds = peak_thresholds(train)
    profile = evaluate(validation, SiteProfile().fit(train).predict(validation), thresholds)
    boosting = evaluate(validation, GradientBoosting().fit(train).predict(validation), thresholds)
    naive = evaluate(validation, SeasonalNaive().predict(validation), thresholds)

    assert boosting["nmae"] == pytest.approx(profile["nmae"], rel=0.1)
    assert boosting["nmae"] < naive["nmae"]


def test_gradient_boosting_unknown_site_is_not_predicted():
    data = add_features(to_hourly_grid(make_mock_like(days=30)))
    model = GradientBoosting().fit(data)
    unknown = data.head(3).assign(site_id="SITE999")
    assert np.isnan(model.predict(unknown)).all()


def test_peak_threshold_relative_to_site_mean():
    train = pd.DataFrame(
        {"site_id": ["bureau"] * 2 + ["datacenter"] * 2, "consumption_kw": [60, 140, 740, 760]}
    )
    thresholds = peak_thresholds(train, ratio=1.25)
    assert thresholds == {"bureau": 125.0, "datacenter": 937.5}


def test_flat_site_has_no_demand_peak():
    data = add_features(to_hourly_grid(make_mock_like(days=30)))
    # Datacenter : consommation plate autour de 735 kW avec 5 % de bruit
    flat = data.assign(consumption_kw=735 * (1 + 0.05 * np.random.default_rng(1).standard_normal(len(data))))
    thresholds = peak_thresholds(flat)
    assert not (flat["consumption_kw"] > flat["site_id"].map(thresholds)).any()


def test_consumption_model_flags_peaks():
    model = ConsumptionModel(SeasonalNaive(), {"A": 50.0, "B": 500.0})
    model_input = pd.DataFrame(
        {"site_id": ["A", "B"], "lag_168": [80.0, 80.0], "lag_24": [np.nan, np.nan]}
    )
    output = model.predict(None, model_input)
    assert output["predicted_kw"].tolist() == [80.0, 80.0]
    assert output["is_peak"].tolist() == [True, False]
