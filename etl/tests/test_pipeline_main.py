"""Point d'entrée python -m pipeline : choix du traitement."""
import json

import pandas as pd

from pipeline.__main__ import JOBS, main


def test_no_argument_or_unknown_job_returns_2(capsys):
    assert main([]) == 2
    assert main(["inexistant"]) == 2
    assert "clean-history" in capsys.readouterr().err


def test_every_declared_job_is_importable():
    import importlib

    for module in JOBS.values():
        assert callable(importlib.import_module(module).main)


def test_runs_the_requested_job(tmp_path, monkeypatch):
    from pipeline.jobs import clean_history

    monkeypatch.setattr(clean_history, "PROVIDED_DIR", tmp_path)
    monkeypatch.setattr(clean_history, "EDITED_DIR", tmp_path)
    input_file, output_file, meta = tmp_path / "in.csv", tmp_path / "out.parquet", tmp_path / "meta.json"
    meta.write_text(json.dumps({"frequency": "1h", "sites": {}}))
    pd.DataFrame(
        {"timestamp": ["2023-01-01 00:00:00"], "site_id": ["SITE001"], "consumption_kwh": [1.0]}
    ).to_csv(input_file, index=False)

    assert main(["clean-history", "--input", str(input_file), "--metadata", str(meta), "--output", str(output_file)]) == 0
    assert len(pd.read_parquet(output_file)) == 1
