from datetime import UTC, datetime

import pandas as pd
import pytest

from enervision_ml.config import parse_data_end
from enervision_ml.predict import check_fresh


def test_data_end_empty_means_no_limit():
    assert parse_data_end(None) is None
    assert parse_data_end("") is None


def test_data_end_defaults_to_utc():
    assert parse_data_end("2025-05-15") == datetime(2025, 5, 15, tzinfo=UTC)


def test_fresh_data_is_accepted():
    now = pd.Timestamp("2026-10-26 12:00", tz="UTC")
    check_fresh(pd.Timestamp("2026-10-26 10:00", tz="UTC"), now)


def test_stale_data_is_refused():
    now = pd.Timestamp("2026-10-26 12:00", tz="UTC")
    with pytest.raises(SystemExit, match="5 h de retard"):
        check_fresh(pd.Timestamp("2026-10-26 07:00", tz="UTC"), now)
