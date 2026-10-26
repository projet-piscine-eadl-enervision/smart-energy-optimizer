"""Découpage temporel et métriques.

Jamais de découpage aléatoire : le modèle doit être évalué sur une période postérieure à
celle qu'il a apprise, comme en production. La validation départage challenger et champion,
le test donne le chiffre final et ne sert à aucune décision.
"""

import numpy as np
import pandas as pd

from enervision_ml.config import TEST_DAYS, VALIDATION_DAYS


def temporal_split(
    df: pd.DataFrame, validation_days: int = VALIDATION_DAYS, test_days: int = TEST_DAYS
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Entraînement | validation | test, dans l'ordre du temps, sans chevauchement."""
    test_start = df["hour"].max() - pd.Timedelta(days=test_days)
    validation_start = test_start - pd.Timedelta(days=validation_days)
    train = df[df["hour"] < validation_start]
    validation = df[(df["hour"] >= validation_start) & (df["hour"] < test_start)]
    test = df[df["hour"] >= test_start]
    return train, validation, test


def evaluate(
    df: pd.DataFrame, predicted_kw: pd.Series, thresholds: dict[str, float]
) -> dict[str, float]:
    """Métriques sur les heures où la mesure réelle et la prévision existent.

    - mae : erreur moyenne en kW, et par site (mae_SITE001…)
    - nmae : erreur relative moyenne des sites ; c'est elle qui départage les modèles,
      pour qu'une usine à 600 kW ne pèse pas plus qu'un bureau à 100 kW
    - coverage : part des heures pour lesquelles le modèle a pu prévoir
    - peak_* : qualité de la détection des pics (précision, rappel, F1)
    """
    actual = df["consumption_kw"]
    predicted = pd.Series(np.asarray(predicted_kw, dtype=float), index=df.index)
    known = actual.notna()
    usable = known & predicted.notna()

    metrics = {"coverage": float(usable.sum() / known.sum()) if known.any() else 0.0}
    errors = (predicted - actual).abs()[usable]
    metrics["mae"] = float(errors.mean())

    site_ids = df.loc[usable, "site_id"]
    nmae_by_site = []
    for site_id, site_errors in errors.groupby(site_ids):
        metrics[f"mae_{site_id}"] = float(site_errors.mean())
        nmae_by_site.append(site_errors.mean() / actual[site_errors.index].mean())
    metrics["nmae"] = float(np.mean(nmae_by_site))

    threshold = df.loc[usable, "site_id"].map(thresholds)
    actual_peak = actual[usable] > threshold
    predicted_peak = predicted[usable] > threshold
    true_positives = int((actual_peak & predicted_peak).sum())
    precision = true_positives / predicted_peak.sum() if predicted_peak.any() else 0.0
    recall = true_positives / actual_peak.sum() if actual_peak.any() else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    metrics.update(peak_precision=float(precision), peak_recall=float(recall), peak_f1=float(f1))
    return metrics
