import numpy as np
import pandas as pd
import pytest

from enervision_ml.evaluate import evaluate, temporal_split


def test_decoupage_temporel_sans_chevauchement(hourly):
    train, validation, test = temporal_split(hourly, validation_days=3, test_days=2)
    assert train["hour"].max() < validation["hour"].min()
    assert validation["hour"].max() < test["hour"].min()
    assert len(train) + len(validation) + len(test) == len(hourly)


def test_metriques_sur_un_cas_simple():
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


def test_couverture_quand_le_modele_ne_peut_pas_prevoir():
    df = pd.DataFrame({"site_id": ["A", "A"], "consumption_kw": [1.0, 2.0]})
    metrics = evaluate(df, pd.Series([1.0, np.nan]), thresholds={"A": 10.0})
    assert metrics["coverage"] == pytest.approx(0.5)
