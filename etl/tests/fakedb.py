"""Fausse connexion psycopg pour tester le code d'écriture sans base.

Elle enregistre chaque requête (texte, paramètres) et répond aux lectures avec les résultats
préparés par le test, dans l'ordre. La vraie base est exercée par les tests d'intégration.
"""
from contextlib import contextmanager


class FakeConnection:
    def __init__(self, results=()):
        self.calls: list[tuple[str, object]] = []
        self.transactions = 0
        self._results = list(results)
        self._current: list = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self._current = self._results.pop(0) if self._results else []
        return self

    def executemany(self, sql, rows):
        self.calls.append((sql, list(rows)))

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return list(self._current)

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield
