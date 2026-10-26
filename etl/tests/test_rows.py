"""Lignes de la base : axe `time` de core.energy_reading, heure du mock, décimaux, ref.site."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mock_client.schemas.reading import Reading
from mock_client.schemas.site import Site
from pipeline.rows import energy_reading_row, site_row, to_decimal
from tests.conftest import READING_PAYLOAD, SITE_EXAMPLE

FETCHED_AT = datetime(2026, 10, 23, 14, 12, 41, tzinfo=UTC)


def reading(**overrides) -> Reading:
    return Reading.model_validate({**READING_PAYLOAD, **overrides})


def test_current_uses_reception_time_as_axis():
    row = energy_reading_row(reading(timestamp="2026-10-23T12:00:00"), "current", FETCHED_AT, raw_id=7)
    assert row["time"] == FETCHED_AT
    assert row["mock_time"] == datetime(2026, 10, 23, 12, 0, tzinfo=UTC)
    assert (row["source"], row["raw_id"]) == ("current", 7)


def test_readings_use_grid_time_as_axis_not_loading_date():
    row = energy_reading_row(reading(timestamp="2024-03-13T08:00:00Z"), "readings", FETCHED_AT)
    assert row["time"] == datetime(2024, 3, 13, 8, 0, tzinfo=UTC)
    assert row["time"] == row["mock_time"]
    assert row["raw_id"] is None


def test_unknown_source_rejected():
    with pytest.raises(ValueError, match="unknown source"):
        energy_reading_row(reading(), "history", FETCHED_AT)


def test_numbers_become_decimals_and_missing_stays_null():
    row = energy_reading_row(reading(consumption_kw=183.61, humidity_percent=None), "current", FETCHED_AT)
    assert row["consumption_kw"] == Decimal("183.61")
    assert isinstance(row["power_factor"], Decimal)
    assert row["humidity_percent"] is None


def test_to_decimal_does_not_keep_float_noise():
    assert to_decimal(0.1 + 0.2) == Decimal("0.30000000000000004")
    assert to_decimal(0.898) == Decimal("0.898")
    assert to_decimal(None) is None


def test_columns_match_core_energy_reading():
    row = energy_reading_row(reading(), "current", FETCHED_AT)
    assert set(row) == {
        "time", "mock_time", "site_id", "consumption_kw", "voltage_v", "current_a", "power_factor",
        "temperature_celsius", "humidity_percent", "null_reasons", "data_quality", "source", "raw_id",
    }  # fmt: skip


def test_site_row_matches_ref_site_columns():
    row = site_row(Site.model_validate(SITE_EXAMPLE))

    assert row == {**SITE_EXAMPLE, "capacity_kw": Decimal("250.0")}
