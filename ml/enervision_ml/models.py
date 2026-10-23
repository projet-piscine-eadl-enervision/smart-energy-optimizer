"""Modèles de prévision et enveloppe MLflow commune.

Chaque modèle expose fit(df) et predict(features) -> kW, la convention de scikit-learn.
ConsumptionModel les enveloppe pour MLflow et ajoute la détection des pics : le service de
prédiction charge le champion sans savoir quel modèle se trouve derrière.
"""

import mlflow
import numpy as np
import pandas as pd

from enervision_ml.config import PEAK_RATIO


class SiteProfile:
    """Consommation moyenne de l'entraînement par site, mois, type de jour et heure.

    Le mock vaut ce profil multiplié par un bruit de 5 % sans mémoire (constats 3 à 5) :
    c'est la meilleure prévision possible, et la référence que tout modèle doit battre.
    Une case jamais vue à l'entraînement (un mois absent) prend la moyenne sans le mois.
    """

    name = "site_profile"
    keys = ("site_id", "month", "is_weekend", "hour_of_day")
    fallback_keys = ("site_id", "is_weekend", "hour_of_day")

    def fit(self, df: pd.DataFrame) -> "SiteProfile":
        known = df.dropna(subset=["consumption_kw"])
        self.profile_ = known.groupby(list(self.keys))["consumption_kw"].mean()
        self.fallback_ = known.groupby(list(self.fallback_keys))["consumption_kw"].mean()
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        keys = pd.MultiIndex.from_frame(features[list(self.keys)])
        fallback_keys = pd.MultiIndex.from_frame(features[list(self.fallback_keys)])
        predicted = self.profile_.reindex(keys)
        fallback = self.fallback_.reindex(fallback_keys)
        return np.where(predicted.isna(), fallback.to_numpy(), predicted.to_numpy())


class SeasonalNaive:
    """Comparaison : même heure la semaine dernière (à défaut, la veille).

    Aucun apprentissage. Sur le mock, il recopie le bruit de la semaine passée et fait moins
    bien que SiteProfile : la preuve que les mesures récentes n'apportent rien (constat 3).
    """

    name = "seasonal_naive"

    def fit(self, df: pd.DataFrame) -> "SeasonalNaive":
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return features["lag_168"].fillna(features["lag_24"]).to_numpy()


MODELS = {model.name: model for model in (SiteProfile, SeasonalNaive)}


def peak_thresholds(train: pd.DataFrame, ratio: float = PEAK_RATIO) -> dict[str, float]:
    """Seuil de pic de demande par site : ratio fois sa consommation moyenne.

    Les heures de forte activité d'un bureau, d'une usine ou d'un commerce le dépassent ;
    un site plat (datacenter, hôpital) n'a pas de pic de demande.
    """
    return (train.groupby("site_id")["consumption_kw"].mean() * ratio).to_dict()


class ConsumptionModel(mlflow.pyfunc.PythonModel):
    """Modèle tel qu'enregistré dans MLflow : prévision en kW et indicateur de pic."""

    def __init__(self, estimator, thresholds: dict[str, float]):
        self.estimator = estimator
        self.thresholds = thresholds

    def predict(self, context, model_input: pd.DataFrame, params=None) -> pd.DataFrame:
        predicted = pd.Series(self.estimator.predict(model_input), index=model_input.index)
        threshold = model_input["site_id"].map(self.thresholds)
        return pd.DataFrame({"predicted_kw": predicted, "is_peak": predicted > threshold})
