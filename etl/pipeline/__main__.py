"""Point d'entrée des traitements : python -m pipeline <traitement> [options].

Traitements disponibles : voir JOBS. Les traitements ponctuels se lancent avec
`docker compose run --rm etl python -m pipeline <traitement>`, ou par un minuteur systemd sur la VM.
"""
import importlib
import sys

# Un traitement = un module de pipeline.jobs qui expose main(argv)
JOBS = {
    "clean-history": "pipeline.jobs.clean_history",
    "load-ref": "pipeline.jobs.load_ref",
    "poll-current": "pipeline.jobs.poll_current",
    "backfill": "pipeline.jobs.backfill",
}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in JOBS:
        print(f"Usage: python -m pipeline {{{'|'.join(JOBS)}}} [options]", file=sys.stderr)
        return 2
    importlib.import_module(JOBS[argv[0]]).main(argv[1:])
    return 0


if __name__ == "__main__":
    sys.exit(main())
