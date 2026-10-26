"""Découpage temporel et métriques.

Jamais de découpage aléatoire : le modèle doit être évalué sur une période postérieure à
celle qu'il a apprise, comme en production. La validation départage challenger et champion,
le test donne le chiffre final et ne sert à aucune décision.
"""

import numpy as np
import pandas as pd

from enervision_ml.config import (
    PEAK_PENALTY_EUR_KWH,
    SHIFTABLE_RATIO,
    TEST_DAYS,
    VALIDATION_DAYS,
)


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
    - kpi_* : impact sur le processus métier simulé (voir business_kpis)
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
    metrics.update(business_kpis(actual[usable], predicted_peak, threshold))
    return metrics


def business_kpis(
    actual: pd.Series,
    predicted_peak: pd.Series,
    threshold: pd.Series,
    shiftable_ratio: float = SHIFTABLE_RATIO,
    penalty_eur_kwh: float = PEAK_PENALTY_EUR_KWH,
) -> dict[str, float]:
    """Impact du modèle sur le processus métier simulé (config.SHIFTABLE_RATIO).

    Sur chaque heure annoncée en pic, le gestionnaire décale shiftable_ratio de la consommation.
    Le dépassement évité est la part du dépassement réel qu'il a pu effacer, en kWh (une heure à
    x kW consomme x kWh). Sans modèle, rien n'est annoncé et rien n'est évité.

    - kpi_peak_kwh_avoided : dépassement évité grâce aux pics annoncés
    - kpi_peak_avoided_ratio : part du dépassement évitable avec une prévision parfaite
    - kpi_penalty_saved_eur : dépassement évité valorisé à penalty_eur_kwh
    - kpi_missed_peak_hours : heures de pic non annoncées (dépassement subi)
    - kpi_false_alarm_hours : heures annoncées sans pic (effort de décalage inutile)
    """
    actual_peak = actual > threshold
    excess = (actual - threshold).clip(lower=0)
    avoidable = np.minimum(excess, shiftable_ratio * actual)
    avoided = float(avoidable[predicted_peak].sum())
    best = float(avoidable.sum())
    return {
        "kpi_peak_kwh_avoided": avoided,
        "kpi_peak_avoided_ratio": avoided / best if best else 0.0,
        "kpi_penalty_saved_eur": avoided * penalty_eur_kwh,
        "kpi_missed_peak_hours": float((actual_peak & ~predicted_peak).sum()),
        "kpi_false_alarm_hours": float((predicted_peak & ~actual_peak).sum()),
    }
