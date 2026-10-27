"""Métriques de l'ETL pour Prometheus, lues dans la base à chaque collecte.

Le collecteur (pipeline poll-current) n'ouvre aucun port : son activité s'observe à travers ce qu'il
écrit, etl.run et core.energy_reading. Les métriques sont donc calculées ici, dans le service etl,
à chaque passage de Prometheus.
"""
import logging
from contextlib import closing

import psycopg
from prometheus_client import CollectorRegistry
from prometheus_client.core import GaugeMetricFamily

from pipeline import db

logger = logging.getLogger(__name__)

# Dernière exécution de chaque traitement (poll_current, ref_load...)
LAST_RUNS = """
    SELECT DISTINCT ON (run_type) run_type, status,
           EXTRACT(EPOCH FROM COALESCE(finished_at, started_at)), rows_loaded, rows_rejected
    FROM etl.run
    ORDER BY run_type, started_at DESC
"""
# Mesure la plus récente reçue : le signal « les données arrivent-elles ? »
LATEST_READING = "SELECT EXTRACT(EPOCH FROM MAX(time)) FROM core.energy_reading"


class EtlCollector:
    """Interroge la base à chaque collecte : aucun état en mémoire, donc aucune valeur périmée."""

    def __init__(self, connect=db.connect):
        self._connect = connect

    def collect(self):
        run_at = GaugeMetricFamily(
            "etl_last_run_timestamp_seconds",
            "Fin de la dernière exécution de chaque traitement, avec son statut",
            labels=["run_type", "status"],
        )
        loaded = GaugeMetricFamily(
            "etl_last_run_rows_loaded", "Lignes chargées par la dernière exécution", labels=["run_type"]
        )
        rejected = GaugeMetricFamily(
            "etl_last_run_rows_rejected", "Lignes rejetées par la dernière exécution", labels=["run_type"]
        )
        reading_at = GaugeMetricFamily(
            "etl_latest_reading_timestamp_seconds", "Heure de réception de la mesure la plus récente"
        )
        up = GaugeMetricFamily("etl_metrics_up", "1 si la base a répondu à la dernière collecte, 0 sinon")
        try:
            with closing(self._connect()) as conn:
                for run_type, status, at, n_loaded, n_rejected in conn.execute(LAST_RUNS).fetchall():
                    run_at.add_metric([run_type, status], float(at))
                    loaded.add_metric([run_type], n_loaded)
                    rejected.add_metric([run_type], n_rejected)
                row = conn.execute(LATEST_READING).fetchone()
                if row and row[0] is not None:
                    reading_at.add_metric([], float(row[0]))
            up.add_metric([], 1)
        except (psycopg.Error, RuntimeError):
            # RuntimeError : DATABASE_URL absente (voir pipeline.db)
            logger.exception("metrics: database unreachable")
            up.add_metric([], 0)
        yield from (run_at, loaded, rejected, reading_at, up)


def build_registry(connect=db.connect) -> CollectorRegistry:
    """Registre propre à l'ETL, plutôt que le registre global : les tests restent indépendants."""
    registry = CollectorRegistry()
    registry.register(EtlCollector(connect))
    return registry
