"""Signal de vivacité du collecteur : un fichier horodaté à chaque tour réussi.

Le HEALTHCHECK du conteneur lance `python -m pipeline.heartbeat` : code 0 si le dernier tour réussi
date de moins de `--max-age` secondes (trois intervalles par défaut), 1 sinon.
"""
import argparse
import os
import sys
import time
from pathlib import Path

DEFAULT_INTERVAL_SECONDS = 60.0


def heartbeat_file() -> Path:
    return Path(os.getenv("HEARTBEAT_FILE", "/tmp/collector.heartbeat"))


def interval_seconds() -> float:
    return float(os.getenv("POLL_INTERVAL_SECONDS") or DEFAULT_INTERVAL_SECONDS)


def beat() -> None:
    heartbeat_file().write_text(str(time.time()), encoding="utf-8")


def age() -> float | None:
    """Secondes depuis le dernier tour réussi, None si le collecteur n'en a encore fait aucun."""
    try:
        return time.time() - float(heartbeat_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--max-age", type=float, default=3 * interval_seconds())
    args = parser.parse_args(argv)
    seconds = age()
    healthy = seconds is not None and seconds <= args.max_age
    print("no successful tour yet" if seconds is None else f"last successful tour {seconds:.0f}s ago")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
