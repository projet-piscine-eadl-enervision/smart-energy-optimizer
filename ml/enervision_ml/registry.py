"""Registre MLflow : un modèle entraîné devient challenger, et champion s'il bat l'actuel.

Règle d'équipe (CONTRIBUTING.md). Le service de prédiction charge toujours l'alias champion.
"""

import mlflow
from mlflow import MlflowClient
from mlflow.entities.model_registry import ModelVersion
from mlflow.exceptions import MlflowException

from enervision_ml.config import MODEL_NAME

CHAMPION = "champion"
CHALLENGER = "challenger"


def get_alias(client: MlflowClient, alias: str) -> ModelVersion | None:
    try:
        return client.get_model_version_by_alias(MODEL_NAME, alias)
    except MlflowException:
        return None


def set_alias(client: MlflowClient, alias: str, version: str) -> None:
    client.set_registered_model_alias(MODEL_NAME, alias, version)


def load_model(version: str) -> mlflow.pyfunc.PyFuncModel:
    return mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{version}")
