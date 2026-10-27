"""Surveillance du modèle : contrôles purs, sans base."""
import numpy as np
import pandas as pd
import pytest

from enervision_ml import monitor
from enervision_ml.config import DRIFT_MIN_HOURS

NOW = pd.Timestamp("2026-10-27 12:00", tz="UTC")
HOURS = pd.date_range(NOW - pd.Timedelta(days=7), NOW - pd.Timedelta(hours=1), freq="h")


def baseline(level=100.0, spread=10.0):
    """Habitude du site : même niveau à toute heure, pour tous les mois et types de jour."""
    rows = [
        {"site_id": "SITE001", "month": m, "day_type": d, "hour": h, "avg_kw": level, "stddev_kw": spread}
        for m in range(1, 13)
        for d in ("weekday", "weekend")
        for h in range(24)
    ]
    return pd.DataFrame(rows)


def recent(shift=0.0, hours=HOURS, missing=0):
    frame = pd.DataFrame(
        {
            "hour": hours,
            "site_id": "SITE001",
            "consumption_kw": 100.0 * (1 + shift),
            "nb_readings": 60,
            "nb_missing": missing,
        }
    )
    return frame


def daily(nmae, days=5):
    return pd.DataFrame({"day": pd.date_range("2026-10-20", periods=days), "site_id": "SITE001", "nmae": nmae})


def status_of(rows, metric):
    return next(r["status"] for r in rows if r["metric"] == metric)


def assess(recent_frame, quality=None, val_nmae=0.04, ages=None):
    return monitor.assess(
        recent_frame,
        baseline(),
        daily(0.04) if quality is None else quality,
        val_nmae,
        {"SITE001": 0.5} if ages is None else ages,
        "1",
        NOW,
    )


def test_stable_data_raises_no_alert():
    rows = assess(recent())

    assert {r["status"] for r in rows} == {"ok"}


def test_a_shifted_level_is_flagged_as_data_drift():
    rows = assess(recent(shift=0.2))

    assert status_of(rows, "level_bias") == "alert"
    assert next(r["value"] for r in rows if r["metric"] == "level_bias") == pytest.approx(0.2)


def test_outliers_are_flagged_when_many_hours_leave_the_usual_range():
    frame = recent()
    frame.loc[frame.index[:30], "consumption_kw"] = 200.0  # 10 écarts types, 30 heures sur 168

    assert status_of(assess(frame), "outlier_share") == "alert"


def test_too_few_hours_is_insufficient_not_ok():
    rows = assess(recent(hours=HOURS[: DRIFT_MIN_HOURS - 1]))

    assert status_of(rows, "level_bias") == "insufficient"
    assert status_of(rows, "outlier_share") == "insufficient"


def test_missing_measures_are_flagged():
    frame = recent(missing=31)  # plus de la moitié des mesures : l'heure ne compte pas (MAX_MISSING_RATIO)

    rows = assess(frame)

    assert status_of(rows, "missing_share") == "alert"
    assert status_of(rows, "level_bias") == "insufficient"  # aucune heure fiable


def test_error_above_the_validation_error_is_concept_drift():
    assert status_of(assess(recent(), quality=daily(0.08)), "nmae_ratio") == "alert"
    assert status_of(assess(recent(), quality=daily(0.05)), "nmae_ratio") == "ok"


def test_not_enough_days_of_error_is_insufficient():
    assert status_of(assess(recent(), quality=daily(0.08, days=2)), "nmae_ratio") == "insufficient"
    assert status_of(assess(recent(), val_nmae=None), "nmae_ratio") == "insufficient"


def test_an_old_prediction_is_flagged_and_an_unknown_one_is_insufficient():
    assert status_of(assess(recent(), ages={"SITE001": 3.5}), "prediction_age_hours") == "alert"
    assert status_of(assess(recent(), ages={}), "prediction_age_hours") == "insufficient"


def test_every_row_has_the_columns_of_the_table():
    row = assess(recent())[0]

    assert set(row) == {"checked_at", "model_version", "site_id", "metric", "value", "threshold", "status"}
    assert not np.isnan(row["threshold"])
