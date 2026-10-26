"""Fausse connexion psycopg pour tester le code d'écriture sans base.

Elle enregistre chaque requête (texte, paramètres) et répond aux lectures soit avec les résultats
préparés par le test, dans l'ordre (`results`), soit par une fonction (`responder(sql, params)`).
La vraie base est exercée par les tests d'intégration.
"""
from contextlib import contextmanager


class FakeConnection:
    def __init__(self, results=(), responder=None):
        self.calls: list[tuple[str, object]] = []
        self.transactions = 0
        self.closed = False
        self.rowcount = 0
        self._results = list(results)
        self._responder = responder
        self._current: list = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self._responder:
            self._current = list(self._responder(sql, params))
        else:
            self._current = self._results.pop(0) if self._results else []
        return self

    def executemany(self, sql, rows):
        rows = list(rows)
        self.calls.append((sql, rows))
        self.rowcount = len(rows)

    def fetchone(self):
        return self._current[0] if self._current else None

    def fetchall(self):
        return list(self._current)

    def cursor(self):
        return self

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    @contextmanager
    def transaction(self):
        self.transactions += 1
        yield
