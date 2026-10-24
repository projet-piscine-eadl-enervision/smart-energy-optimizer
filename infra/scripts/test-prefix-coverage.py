#!/usr/bin/env python3
"""Vérifie prefix-coverage.py. Lancé par la CI."""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("prefix_coverage", pathlib.Path(__file__).with_name("prefix-coverage.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

source = (
    '<coverage><packages><package name="app"><classes>'
    '<class name="main.py" filename="app/main.py" line-rate="1"><lines/></class>'
    '<class name="x.py" filename="app/api/x.py"><lines/></class>'
    "</classes></package></packages></coverage>"
)
result = module.prefix(source, "api")
assert 'filename="api/app/main.py"' in result, result
assert 'filename="api/app/api/x.py"' in result, result
assert 'name="main.py"' in result and 'name="app"' in result, "seuls les chemins changent"
print("ok   prefix-coverage : chemins préfixés, noms inchangés")
