"""Chargement sur le vrai parquet nettoyé : ignoré tant que `dvc pull` puis `dvc repro` n'ont pas été faits."""
from collections import Counter

import pytest

from pipeline.jobs import clean_history, load_history
from pipeline.rows import history_rows

pytestmark = pytest.mark.skipif(
    not clean_history.DEFAULT_OUTPUT.exists(), reason="parquet missing: run dvc pull then dvc repro"
)

ALERT_TYPES = {"spike", "threshold", "anomaly", "outage", "sensor", "plateau", "drop"}  # ref.alert_type
SEVERITIES = {"low", "medium", "high", "critical"}  # ref.severity


@pytest.fixture(scope="module")
def rows():
    return history_rows(load_history.read_history(clean_history.DEFAULT_OUTPUT))


def test_every_row_is_loadable(rows):
    accepted, rejected = load_history.split_rows(rows, ALERT_TYPES, SEVERITIES)

    assert len(accepted) == 122647 and not rejected


def test_missing_consumption_is_null_and_anomalies_are_kept(rows):
    assert sum(row["consumption_kw"] is None for row in rows) == 1441
    assert Counter(row["anomaly_type"] for row in rows) == {
        None: 111241, "plateau": 8315, "outage": 1932, "drop": 590, "spike": 569,
    }
    assert {row["site_id"] for row in rows} == {f"SITE00{n}" for n in range(1, 8)}
