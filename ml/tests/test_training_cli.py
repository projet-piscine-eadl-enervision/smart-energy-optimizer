"""Le module se lance en ligne de commande, comme le fait le minuteur d’entraînement."""
import runpy
import sys

import pytest


def test_module_runs_its_main_when_executed(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["enervision_ml.training", "--help"])
    sys.modules.pop("enervision_ml.training", None)
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("enervision_ml.training", run_name="__main__")
    assert exit_info.value.code == 0
    assert "--trigger" in capsys.readouterr().out
