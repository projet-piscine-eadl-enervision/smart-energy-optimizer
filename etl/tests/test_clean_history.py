"""Nettoyage de l'historique : règles (cleaning) et traitement complet (jobs.clean_history)."""
import base64
import json

import numpy as np
import pandas as pd
import pytest

from pipeline import cleaning as ch
from pipeline.jobs import clean_history as job
from tests.conftest import NAN, make_anomaly, make_metadata, make_readings


def test_kwh_recovered_from_euros_at_measured_tariff():
    df = ch.clean(make_readings([100.0, NAN, 100.0], euros=[15.0, 30.0, 15.0]))
    assert df.loc[1, "consumption_kwh_clean"] == pytest.approx(200.0)  # 30 / 0,15
    assert df.loc[1, "consumption_kwh_source"] == ch.SOURCE_RECOVERED


def test_raw_value_never_overwritten():
    df = ch.clean(make_readings([100.0, NAN, 120.0]))
    assert np.isnan(df.loc[1, "consumption_kwh"])
    assert df.loc[1, "consumption_kwh_clean"] == pytest.approx(110.0)
    assert df.loc[1, "consumption_kwh_source"] == ch.SOURCE_INTERPOLATED


def test_zeros_are_real_outages_and_kept():
    df = ch.clean(make_readings([100.0, 0.0, 0.0, 100.0], euros=[15.0, 0.0, 0.0, 15.0]))
    assert df["consumption_kwh_clean"].tolist() == [100.0, 0.0, 0.0, 100.0]
    assert set(df["consumption_kwh_source"]) == {ch.SOURCE_MEASURED}


def test_short_gap_interpolated_long_gap_left_empty():
    short_gap = [10.0, NAN, NAN, NAN, NAN, 20.0]  # 4 valeurs : limite incluse
    long_gap = [10.0, NAN, NAN, NAN, NAN, NAN, 20.0]  # 5 valeurs : au-delà
    assert ch.clean(make_readings(short_gap))["consumption_kwh_clean"].notna().all()

    df = ch.clean(make_readings(long_gap))
    assert df["consumption_kwh_clean"].iloc[1:6].isna().all()
    assert (df["consumption_kwh_source"].iloc[1:6] == ch.SOURCE_MISSING).all()


def test_never_filled_with_zero_nor_extrapolated():
    df = ch.clean(make_readings([NAN, 10.0, 20.0, NAN]))
    assert np.isnan(df.loc[0, "consumption_kwh_clean"])
    assert np.isnan(df.loc[3, "consumption_kwh_clean"])


def test_interpolation_isolated_per_site():
    a = make_readings([10.0, NAN], site="SITE001")
    b = make_readings([30.0, 50.0], site="SITE002")
    df = ch.clean(pd.concat([a, b], ignore_index=True))
    site1 = df[df.site_id == "SITE001"]
    assert np.isnan(site1["consumption_kwh_clean"].iloc[1])  # pas de valeur voisine du même site


def test_duplicates_removed_and_sorted_by_time():
    df = make_readings([3.0, 1.0, 2.0])
    df = pd.concat([df.iloc[[2, 0, 1]], df.iloc[[0]]], ignore_index=True)
    result = ch.clean(df)
    assert len(result) == 3
    assert result["timestamp"].is_monotonic_increasing


def test_no_interpolation_inside_labelled_outage():
    meta = make_metadata([make_anomaly("2023-01-01T01:00:00", "outage", "Coupure électrique (1h)")])
    df = ch.clean(make_readings([10.0, NAN, 30.0, NAN, 50.0]), meta)
    assert np.isnan(df.loc[1, "consumption_kwh_clean"])  # dans la coupure : laissé vide
    assert df.loc[1, "consumption_kwh_source"] == ch.SOURCE_MISSING
    assert df.loc[3, "consumption_kwh_clean"] == pytest.approx(40.0)  # hors coupure : interpolé


def test_euros_recover_a_value_even_in_an_outage():
    meta = make_metadata([make_anomaly("2023-01-01T01:00:00", "outage", "Coupure électrique (1h)")])
    df = ch.clean(make_readings([10.0, NAN, 30.0], euros=[1.5, 0.0, 4.5]), meta)
    assert df.loc[1, "consumption_kwh_clean"] == 0.0
    assert df.loc[1, "consumption_kwh_source"] == ch.SOURCE_RECOVERED


def test_no_anomaly_columns_without_metadata():
    assert "anomaly_type" not in ch.clean(make_readings([1.0, 2.0]))


@pytest.fixture
def allowed_dirs(tmp_path, monkeypatch):
    """Point the allowed input and output folders of the job to tmp_path."""
    monkeypatch.setattr(job, "PROVIDED_DIR", tmp_path)
    monkeypatch.setattr(job, "EDITED_DIR", tmp_path)
    return tmp_path


@pytest.mark.usefixtures("allowed_dirs")
def test_cli_writes_parquet_with_anomalies(tmp_path):
    input_file, meta, output_file = tmp_path / "in.csv", tmp_path / "meta.json", tmp_path / "sortie" / "out.parquet"
    make_readings([1.0, NAN, 3.0]).to_csv(input_file, index=False)
    meta.write_text(json.dumps(make_metadata([make_anomaly("2023-01-01T01:00:00", "outage", "Coupure (1h)")])))

    job.main(["--input", str(input_file), "--metadata", str(meta), "--output", str(output_file)])

    written = pd.read_parquet(output_file)
    assert {"consumption_kwh", "consumption_kwh_clean", "consumption_kwh_source", "anomaly_type"} <= set(written)
    assert len(written) == 3
    assert written["anomaly_type"].isna().tolist() == [True, False, True]
    assert written.loc[1, "anomaly_type"] == "outage"


@pytest.mark.usefixtures("allowed_dirs")
def test_cli_fails_without_metadata_file(tmp_path):
    input_file = tmp_path / "in.csv"
    make_readings([1.0]).to_csv(input_file, index=False)
    with pytest.raises(FileNotFoundError):
        job.main(["--input", str(input_file), "--metadata", str(tmp_path / "absent.json"), "--output", str(tmp_path / "o.parquet")])


@pytest.mark.parametrize(
    "problem, expected",
    [
        ("mismatch", "difference with the metadata: mismatch"),
        ("site_1: 3 rows\n2 announced", "problem: " + str(base64.b64encode(b"site_1: 3 rows\n2 announced"))),
    ],
)
def test_cli_logs_metadata_problems(allowed_dirs, monkeypatch, caplog, problem, expected):
    """Alphanumeric problems are logged as is, the others base64-encoded (no log injection)."""
    input_file, meta = allowed_dirs / "in.csv", allowed_dirs / "meta.json"
    make_readings([1.0, 2.0]).to_csv(input_file, index=False)
    meta.write_text(json.dumps(make_metadata([])))
    monkeypatch.setattr(job, "check_against_metadata", lambda df, metadata: [problem])

    with caplog.at_level("WARNING"):
        job.main(["--input", str(input_file), "--metadata", str(meta), "--output", str(allowed_dirs / "o.parquet")])

    assert [r.getMessage() for r in caplog.records if r.levelname == "WARNING"] == [expected]
    assert "metadata check: totals" not in caplog.text


@pytest.mark.parametrize(
    "option, value",
    [
        ("--output", "../../tmp/x.parquet"),
        ("--input", "../outside.csv"),
        ("--metadata", "/etc/meta.json"),
        ("--output", "out.csv"),
        ("--input", "in.txt"),
    ],
)
def test_cli_rejects_path_outside_allowed_dir_or_bad_extension(allowed_dirs, capsys, option, value):
    path = value if value.startswith("/") else str(allowed_dirs / value)
    with pytest.raises(SystemExit) as exc:
        job.main([option, path])
    assert exc.value.code == 2
    assert option in capsys.readouterr().err
    assert not (allowed_dirs.parent.parent / "tmp" / "x.parquet").exists()


def test_default_paths_are_accepted():
    parser = job.argparse.ArgumentParser()
    assert job.checked_path(parser, "--input", job.DEFAULT_INPUT, job.PROVIDED_DIR, ".csv") == job.DEFAULT_INPUT
    assert job.checked_path(parser, "--metadata", job.DEFAULT_METADATA, job.PROVIDED_DIR, ".json") == job.DEFAULT_METADATA
    assert job.checked_path(parser, "--output", job.DEFAULT_OUTPUT, job.EDITED_DIR, ".parquet") == job.DEFAULT_OUTPUT


def test_duplicates_and_irregular_intervals_logged(caplog):
    df = make_readings([1.0, 2.0, 3.0])
    df = pd.concat([df, df.iloc[[0]], make_readings([4.0], start="2023-01-01 05:00:00")], ignore_index=True)
    with caplog.at_level("WARNING"):
        ch.clean(df)
    assert "duplicates" in caplog.text
    assert "intervals different" in caplog.text
