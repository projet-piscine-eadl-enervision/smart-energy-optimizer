import numpy as np
import pandas as pd
import pytest

from enervision_ml.evaluate import business_kpis, evaluate, temporal_split


def test_temporal_split_without_overlap(hourly):
    train, validation, test = temporal_split(hourly, validation_days=3, test_days=2)
    assert train["hour"].max() < validation["hour"].min()
    assert validation["hour"].max() < test["hour"].min()
    assert len(train) + len(validation) + len(test) == len(hourly)


def test_metrics_on_simple_case():
    df = pd.DataFrame(
        {
            "site_id": ["A", "A", "B", "B"],
            "consumption_kw": [100.0, 200.0, 10.0, np.nan],
        }
    )
    predicted = pd.Series([110.0, 190.0, 12.0, 50.0])
    metrics = evaluate(df, predicted, thresholds={"A": 150.0, "B": 100.0})

    assert metrics["mae_A"] == pytest.approx(10.0)
    assert metrics["mae_B"] == pytest.approx(2.0)
    # nMAE = moyenne des erreurs relatives par site : (10/150 + 2/10) / 2
    assert metrics["nmae"] == pytest.approx((10 / 150 + 2 / 10) / 2)
    # La mesure manquante de B est ignorée : 3 heures utilisables sur 3 connues
    assert metrics["coverage"] == pytest.approx(1.0)
    # Un vrai pic (A à 200) correctement annoncé, aucune fausse alerte
    assert metrics["peak_precision"] == 1.0
    assert metrics["peak_recall"] == 1.0


def test_coverage_when_model_cannot_predict():
    df = pd.DataFrame({"site_id": ["A", "A"], "consumption_kw": [1.0, 2.0]})
    metrics = evaluate(df, pd.Series([1.0, np.nan]), thresholds={"A": 10.0})
    assert metrics["coverage"] == pytest.approx(0.5)


def test_kpi_metier_sur_un_cas_simple():
    # Seuil 100 kW. Heure 1 : pic de 150 kW annoncé ; heure 2 : pic de 105 kW manqué ;
    # heure 3 : fausse alerte ; heure 4 : rien
    actual = pd.Series([150.0, 105.0, 90.0, 80.0])
    predicted_peak = pd.Series([True, False, True, False])
    threshold = pd.Series([100.0] * 4)
    kpis = business_kpis(actual, predicted_peak, threshold, shiftable_ratio=0.1, penalty_eur_kwh=2.0)

    # Heure 1 : dépassement 50 kWh, on ne sait décaler que 10 % de 150 = 15 kWh
    assert kpis["kpi_peak_kwh_avoided"] == pytest.approx(15.0)
    # Avec une prévision parfaite : 15 + min(5, 10,5) = 20 kWh
    assert kpis["kpi_peak_avoided_ratio"] == pytest.approx(15.0 / 20.0)
    assert kpis["kpi_penalty_saved_eur"] == pytest.approx(30.0)
    assert kpis["kpi_missed_peak_hours"] == 1
    assert kpis["kpi_false_alarm_hours"] == 1


def test_sans_pic_annonce_rien_n_est_evite():
    actual = pd.Series([150.0, 120.0])
    kpis = business_kpis(actual, pd.Series([False, False]), pd.Series([100.0, 100.0]))
    assert kpis["kpi_peak_kwh_avoided"] == 0.0
    assert kpis["kpi_penalty_saved_eur"] == 0.0
    assert kpis["kpi_missed_peak_hours"] == 2
