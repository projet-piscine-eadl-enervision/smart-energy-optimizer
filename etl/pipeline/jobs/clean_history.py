"""Traitement : nettoie l'historique fourni par l'école et écrit le parquet.

Usage, depuis etl/ :
    python -m pipeline clean-history [--input CSV] [--metadata JSON] [--output PARQUET]
"""
import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from pipeline.cleaning import CONSUMPTION_COL, WEATHER_COLS, clean
from pipeline.metadata import check_against_metadata

logger = logging.getLogger(__name__)

PIPELINE_DIR = Path(__file__).resolve().parents[1]
PROVIDED_DIR = PIPELINE_DIR / "provided_files"
EDITED_DIR = PIPELINE_DIR / "edited_files"
DEFAULT_INPUT = PROVIDED_DIR / "all_sites_combined.csv"
DEFAULT_METADATA = PROVIDED_DIR / "dataset_metadata.json"
DEFAULT_OUTPUT = EDITED_DIR / "energy_consumption_cleaned.parquet"


def summarize(df: pd.DataFrame) -> None:
    for col in [CONSUMPTION_COL, *WEATHER_COLS]:
        if f"{col}_source" in df:
            logger.info("%s: %s", col, df[f"{col}_source"].value_counts().to_dict())
    if "anomaly_type" in df:
        logger.info("labelled anomalies (rows): %s", df["anomaly_type"].value_counts().to_dict())


def checked_path(
    parser: argparse.ArgumentParser, option: str, path: Path, allowed_dir: Path, suffix: str
) -> Path:
    """Resolve the path and reject it outside allowed_dir or with another extension (Sonar S8707)."""
    resolved = path.resolve()
    if not resolved.is_relative_to(allowed_dir.resolve()):
        parser.error(f"{option} must be inside {allowed_dir}: {path}")
    if resolved.suffix.lower() != suffix:
        parser.error(f"{option} must be a {suffix} file: {path}")
    return resolved


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    input_path = checked_path(parser, "--input", args.input, PROVIDED_DIR, ".csv")
    metadata_path = checked_path(parser, "--metadata", args.metadata, PROVIDED_DIR, ".json")
    output_path = checked_path(parser, "--output", args.output, EDITED_DIR, ".parquet")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger.info("Reading %s and %s", input_path, metadata_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    cleansed = clean(pd.read_csv(input_path), metadata)

    problems = check_against_metadata(cleansed, metadata)
    for problem in problems:
        logger.warning("difference with the metadata: %s", problem)
    if not problems:
        logger.info("metadata check: totals, periods and frequency match")
    summarize(cleansed)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cleansed.to_parquet(output_path, engine="pyarrow", index=False)
    logger.info("%d rows written to %s", len(cleansed), output_path)
