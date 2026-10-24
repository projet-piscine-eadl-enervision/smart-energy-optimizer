#!/usr/bin/env python3
"""Rend un coverage.xml lisible par Sonar depuis la racine du dépôt.

pytest tourne dans le dossier du module (api/, etl/, ml/) : coverage.py y écrit des chemins relatifs
à ce dossier (app/main.py). Sonar analyse depuis la racine et attend api/app/main.py. Le script
préfixe donc chaque chemin avec le dossier du module.

Usage : prefix-coverage.py <coverage.xml> <dossier-du-module>
"""
import re
import sys


def prefix(xml: str, module: str) -> str:
    # <source> : coverage.py y écrit le chemin absolu du dossier du module, qui existe sur le
    # runner. Sonar s'en sert alors comme seule racine et ne retrouve plus api/app/main.py
    # (« Cannot resolve the file path »). « . » le fait résoudre depuis la racine du dépôt.
    xml = re.sub(r"<source>[^<]*</source>", "<source>.</source>", xml)
    return re.sub(r'(<class [^>]*?filename=")([^"]+)(")', lambda m: f"{m.group(1)}{module}/{m.group(2)}{m.group(3)}", xml)


if __name__ == "__main__":
    path, module = sys.argv[1], sys.argv[2].strip("/")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    with open(path, "w", encoding="utf-8") as f:
        f.write(prefix(text, module))
