#!/usr/bin/env python3
"""Synchronise la documentation du dépôt vers le wiki GitHub, à sens unique.

Le dépôt est la source : les pages listées dans docs/wiki-map.toml sont régénérées à chaque
passage, avec un bandeau « page générée » et des liens réécrits vers les autres pages du wiki.
Le script ne touche qu'aux pages qu'il a lui-même générées (première ligne `<!-- sync-wiki:`) :
Home.md et les dailys (Daily-AAAA-MM-JJ.md), écrits à la main dans le wiki, sont conservés.
Il régénère aussi _Sidebar.md et Dailys.md (index des dailys présents dans le wiki).

Usage :
  sync-wiki.py --check                     vérifie la table contre les fichiers versionnés
  sync-wiki.py --wiki-dir <dossier-wiki>   écrit les pages dans un clone du wiki (sans commit)
"""
import argparse
import os
import pathlib
import posixpath
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass

MARKER = "<!-- sync-wiki:"
DAILY = re.compile(r"^Daily-(\d{4})-(\d{2})-(\d{2})\.md$")
MONTHS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp")
TITLE = re.compile(r"^[\w ]+$")
INLINE_LINK = re.compile(r"(\]\()([^)\s]+)((?:\s+\"[^\"]*\")?\))")
REFERENCE_LINK = re.compile(r"^(\[[^\]]+\]:\s+)(\S+)", re.MULTILINE)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


@dataclass(frozen=True)
class Entry:
    source: str
    title: str
    section: str
    optional: bool = False

    @property
    def page(self) -> str:
        """Nom de la page dans le wiki (sans extension)."""
        return self.title.replace(" ", "-")


def load_map(path: pathlib.Path) -> tuple[str, list[str], list[Entry]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries = [
        Entry(p["source"], p["title"], p["section"], p.get("optional", False))
        for p in data.get("page", [])
    ]
    return data.get("repo", ""), data.get("ignore", []), entries


def is_documentation(path: str) -> bool:
    name = posixpath.basename(path)
    return (
        name in ("README.md", "CONTRIBUTING.md", "SECURITY.md")
        and (name == "README.md" or "/" not in path)
    ) or (path.startswith("docs/") and path.endswith(".md"))


def check(entries: list[Entry], ignore: list[str], tracked: list[str]) -> list[str]:
    """Liste les écarts entre la table et les fichiers versionnés (vide si tout est cohérent)."""
    errors = []
    sources = [e.source for e in entries]
    pages = [e.page for e in entries]
    for value in {s for s in sources if sources.count(s) > 1}:
        errors.append(f"source listed twice: {value}")
    for value in {p for p in pages if pages.count(p) > 1}:
        errors.append(f"page name used twice: {value}")
    reserved = {"Home", "Dailys", "_Sidebar"}
    for entry in entries:
        if not TITLE.match(entry.title):
            errors.append(f"invalid title (letters, digits and spaces only): {entry.title!r}")
        if entry.page in reserved or DAILY.match(entry.page + ".md"):
            errors.append(f"reserved page name: {entry.page}")
        if entry.source not in tracked and not entry.optional:
            errors.append(f"missing file: {entry.source}")
    mapped = set(sources) | set(ignore)
    for path in tracked:
        if is_documentation(path) and path not in mapped:
            errors.append(f"documentation not in docs/wiki-map.toml: {path}")
    return errors


def rewrite_target(target: str, source: str, by_source: dict[str, Entry], repo: str,
                   root: pathlib.Path) -> str:
    """Réécrit une cible de lien relative au fichier source ; les autres cibles restent telles quelles."""
    path, hash_, fragment = target.partition("#")
    if not path or SCHEME.match(path) or path.startswith("//"):
        return target
    if path.startswith("/"):
        joined = posixpath.normpath(path.lstrip("/"))
    else:
        joined = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if joined.startswith(".."):
        return target
    if joined in by_source:
        return by_source[joined].page + hash_ + fragment
    local = root / joined
    if not local.exists():
        return target
    base = f"https://github.com/{repo}"
    if local.is_dir():
        return f"{base}/tree/main/{joined}{hash_}{fragment}"
    if joined.lower().endswith(IMAGE_SUFFIXES):
        return f"https://raw.githubusercontent.com/{repo}/main/{joined}"
    return f"{base}/blob/main/{joined}{hash_}{fragment}"


def rewrite_links(text: str, source: str, by_source: dict[str, Entry], repo: str,
                  root: pathlib.Path) -> str:
    """Réécrit les liens hors blocs de code (``` et ~~~)."""
    def inline(match: re.Match) -> str:
        return match[1] + rewrite_target(match[2], source, by_source, repo, root) + match[3]

    def reference(match: re.Match) -> str:
        return match[1] + rewrite_target(match[2], source, by_source, repo, root)

    out, fence, block = [], None, []

    def flush() -> None:
        if block:
            chunk = "\n".join(block)
            out.append(REFERENCE_LINK.sub(reference, INLINE_LINK.sub(inline, chunk)))
            block.clear()

    for line in text.split("\n"):
        stripped = line.lstrip()
        if fence is None and stripped.startswith(("```", "~~~")):
            flush()
            fence = stripped[:3]
            out.append(line)
        elif fence is not None:
            out.append(line)
            if stripped.startswith(fence):
                fence = None
        else:
            block.append(line)
    flush()
    return "\n".join(out)


def render_page(entry: Entry, text: str, by_source: dict[str, Entry], repo: str,
                root: pathlib.Path) -> str:
    banner = (
        f"{MARKER} généré depuis {entry.source}, ne pas modifier ici -->\n"
        f"> Page générée depuis [`{entry.source}`](https://github.com/{repo}/blob/main/{entry.source}). "
        "Pour la modifier, ouvrir une pull request sur le dépôt.\n\n"
    )
    return banner + rewrite_links(text, entry.source, by_source, repo, root)


def list_dailys(wiki_dir: pathlib.Path) -> list[tuple[str, str]]:
    """Dailys présents dans le wiki, du plus récent au plus ancien : (page, date lisible)."""
    found = []
    for path in wiki_dir.glob("Daily-*.md"):
        match = DAILY.match(path.name)
        if match:
            year, month, day = match.groups()
            label = f"{int(day)} {MONTHS[int(month) - 1]} {year}"
            found.append((path.stem, label))
    return sorted(found, reverse=True)


def render_dailys(dailys: list[tuple[str, str]]) -> str:
    lines = [
        f"{MARKER} généré depuis les pages Daily-*, ne pas modifier ici -->",
        "# Dailys", "",
        "Comptes rendus des réunions quotidiennes, du plus récent au plus ancien.", "",
    ]
    lines += [f"- [{label}]({page})" for page, label in dailys]
    return "\n".join(lines) + "\n"


def render_sidebar(entries: list[Entry], dailys: list[tuple[str, str]], available: set[str]) -> str:
    lines = [f"{MARKER} généré par infra/scripts/sync-wiki.py, ne pas modifier ici -->", "**[Accueil](Home)**", ""]
    sections: dict[str, list[Entry]] = {}
    for entry in entries:
        if entry.source in available:
            sections.setdefault(entry.section, []).append(entry)
    for section, items in sections.items():
        lines += [f"**{section}**", ""]
        lines += [f"- [{e.title}]({e.page})" for e in items]
        lines.append("")
    lines += ["**[Dailys](Dailys)**", ""]
    lines += [f"- [{label}]({page})" for page, label in dailys]
    return "\n".join(lines) + "\n"


def write_if_changed(path: pathlib.Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def sync(root: pathlib.Path, wiki_dir: pathlib.Path, repo: str, entries: list[Entry]) -> tuple[int, int]:
    """Écrit les pages dans wiki_dir ; renvoie (pages écrites ou modifiées, pages obsolètes supprimées)."""
    available = {e.source for e in entries if (root / e.source).is_file()}
    by_source = {e.source: e for e in entries if e.source in available}
    generated: set[str] = set()
    changed = 0
    for entry in by_source.values():
        text = (root / entry.source).read_text(encoding="utf-8")
        name = f"{entry.page}.md"
        generated.add(name)
        changed += write_if_changed(wiki_dir / name, render_page(entry, text, by_source, repo, root))
    dailys = list_dailys(wiki_dir)
    for name, content in (
        ("Dailys.md", render_dailys(dailys)),
        ("_Sidebar.md", render_sidebar(entries, dailys, available)),
    ):
        generated.add(name)
        changed += write_if_changed(wiki_dir / name, content)
    removed = 0
    for path in wiki_dir.glob("*.md"):
        first = path.read_text(encoding="utf-8").split("\n", 1)[0]
        if first.startswith(MARKER) and path.name not in generated:
            path.unlink()
            removed += 1
    return changed, removed


def tracked_files(root: pathlib.Path) -> list[str]:
    result = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="check the page map against tracked files")
    parser.add_argument("--wiki-dir", type=pathlib.Path, help="wiki clone to write the pages into")
    parser.add_argument("--map", type=pathlib.Path, default=None, help="page map (default: docs/wiki-map.toml)")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="OWNER/NAME of the repository")
    args = parser.parse_args()

    root = pathlib.Path(__file__).resolve().parents[2]
    repo_map, ignore, entries = load_map(args.map or root / "docs" / "wiki-map.toml")
    repo = args.repo or repo_map
    if not args.check and not args.wiki_dir:
        parser.error("--check or --wiki-dir is required")

    errors = check(entries, ignore, tracked_files(root))
    if errors:
        print("\n".join(f"error: {e}" for e in errors), file=sys.stderr)
        return 1
    if args.check:
        print(f"ok: {len(entries)} pages mapped")
        return 0

    changed, removed = sync(root, args.wiki_dir, repo, entries)
    print(f"{changed} pages written, {removed} obsolete pages removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
