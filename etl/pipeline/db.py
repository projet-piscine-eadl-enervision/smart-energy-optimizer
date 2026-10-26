"""Connexion à la base : une variable d'environnement, DATABASE_URL."""
import os

import psycopg


def database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set")
    return url


def connect() -> psycopg.Connection:
    """Connexion en autocommit : chaque écriture se fait dans un `with conn.transaction()` explicite.

    Le suivi des exécutions (pipeline.runs) reste ainsi enregistré même si le traitement échoue.
    """
    return psycopg.connect(database_url(), autocommit=True)
