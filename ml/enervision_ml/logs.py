"""Journal du module : sur la sortie standard, donc dans journald (journalctl) et dans les tests.

Chaque événement porte la version du modèle (et le run MLflow pour l'entraînement). Jamais l'adresse
de la base : elle contient le mot de passe.
"""
import logging
import sys


def configure(level: int = logging.INFO) -> None:
    logger = logging.getLogger("enervision_ml")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
