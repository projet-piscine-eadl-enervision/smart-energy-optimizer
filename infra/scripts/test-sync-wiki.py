#!/usr/bin/env python3
"""Vérifie sync-wiki.py. Lancé par le workflow wiki."""
import importlib.util
import pathlib
import tempfile

spec = importlib.util.spec_from_file_location("sync_wiki", pathlib.Path(__file__).with_name("sync-wiki.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

REPO = "org/projet"
ENTRIES = [
    module.Entry("README.md", "Présentation", "Démarrer"),
    module.Entry("docs/deploiement.md", "Déploiement", "Exploitation"),
    module.Entry("docs/migrations.md", "Migrations", "Exploitation"),
    module.Entry("ml/README.md", "ML", "Modules", optional=True),
]


def make_root(tmp: pathlib.Path) -> pathlib.Path:
    root = tmp / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "etl").mkdir()
    (root / "etl" / "run.py").write_text("print(1)\n")
    (root / "docs" / "schema.png").write_bytes(b"png")
    (root / "README.md").write_text("# Titre\n\nVoir [le déploiement](docs/deploiement.md#etapes).\n")
    (root / "docs" / "deploiement.md").write_text(
        "# Déploiement\n\n"
        "[migrations](migrations.md) | [accueil](../README.md) | [script](../etl/run.py) | [dossier](../etl) | "
        "[web](https://exemple.org/a.md) | [ancre](#etapes) | [absent](inconnu.md) | [dehors](../../x.md)\n"
        "![schéma](schema.png)\n\n"
        "```\n[dans un bloc](migrations.md)\n```\n\n"
        "[ref]: migrations.md\n"
    )
    (root / "docs" / "migrations.md").write_text("# Migrations\n")
    return root


def test_links() -> None:
    with tempfile.TemporaryDirectory() as raw:
        root = make_root(pathlib.Path(raw))
        by_source = {e.source: e for e in ENTRIES}
        text = (root / "docs" / "deploiement.md").read_text()
        out = module.rewrite_links(text, "docs/deploiement.md", by_source, REPO, root)
        assert "](Migrations)" in out, out
        assert "](Présentation)" in out, "lien vers un fichier de la table"
        assert f"](https://github.com/{REPO}/blob/main/etl/run.py)" in out, out
        assert f"](https://github.com/{REPO}/tree/main/etl)" in out, out
        assert f"](https://raw.githubusercontent.com/{REPO}/main/docs/schema.png)" in out, out
        assert "](https://exemple.org/a.md)" in out and "](#etapes)" in out, "liens externes et ancres seules"
        assert "](inconnu.md)" in out and "](../../x.md)" in out, "cibles introuvables laissées telles quelles"
        assert "[dans un bloc](migrations.md)" in out, "bloc de code intact"
        assert "[ref]: Migrations" in out, "lien de référence"
        readme = module.rewrite_links((root / "README.md").read_text(), "README.md", by_source, REPO, root)
        assert "](Déploiement#etapes)" in readme, readme
    print("ok   sync-wiki : liens vers pages, code, dossiers, images, externes, blocs de code")


def test_check() -> None:
    tracked = ["README.md", "docs/deploiement.md", "docs/migrations.md", "etl/README.md", "SECURITY.md",
               "frontend/src/x.md", "sub/CONTRIBUTING.md"]
    errors = module.check(ENTRIES, [], tracked)
    assert errors == [
        "documentation not in docs/wiki-map.toml: etl/README.md",
        "documentation not in docs/wiki-map.toml: SECURITY.md",
    ], errors
    assert module.check(ENTRIES, ["etl/README.md", "SECURITY.md"], tracked) == []
    assert not module.check(ENTRIES, ["etl/README.md", "SECURITY.md"], tracked + ["ml/README.md"])
    missing = module.check(ENTRIES, ["etl/README.md"], ["README.md", "docs/deploiement.md"])
    assert missing == ["missing file: docs/migrations.md"], missing
    bad = [module.Entry("README.md", "Home", "x"), module.Entry("a.md", "A-b", "x"), module.Entry("README.md", "Autre", "x")]
    errors = module.check(bad, [], ["README.md", "a.md"])
    assert any("reserved" in e for e in errors) and any("invalid title" in e for e in errors), errors
    assert any("listed twice" in e for e in errors), errors
    print("ok   sync-wiki : table cohérente, page absente, optionnel, titres invalides et doublons")


def test_sync() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = pathlib.Path(raw)
        root = make_root(tmp)
        wiki = tmp / "wiki"
        wiki.mkdir()
        (wiki / "Home.md").write_text("Accueil écrit à la main\n")
        (wiki / "Daily-2026-10-22.md").write_text("<html>daily</html>\n")
        (wiki / "Daily-2026-10-23.md").write_text("# daily\n")
        (wiki / "Ancienne-page.md").write_text(f"{module.MARKER} généré depuis x.md, ne pas modifier ici -->\nvieux\n")
        (wiki / "Page-manuelle.md").write_text("# écrite à la main\n")

        changed, removed = module.sync(root, wiki, REPO, ENTRIES)
        assert (changed, removed) == (5, 1), (changed, removed)
        assert (wiki / "Home.md").read_text() == "Accueil écrit à la main\n", "Home.md intact"
        assert (wiki / "Daily-2026-10-22.md").read_text() == "<html>daily</html>\n", "dailys intacts"
        assert (wiki / "Page-manuelle.md").exists(), "page sans marqueur conservée"
        assert not (wiki / "Ancienne-page.md").exists(), "page générée obsolète supprimée"
        assert not (wiki / "ML.md").exists(), "page optionnelle absente ignorée"
        page = (wiki / "Déploiement.md").read_text()
        assert page.startswith(module.MARKER) and "docs/deploiement.md" in page.split("\n")[1], page

        sidebar = (wiki / "_Sidebar.md").read_text()
        assert "[Déploiement](Déploiement)" in sidebar and "ML" not in sidebar, sidebar
        assert sidebar.index("[23 octobre 2026](Daily-2026-10-23)") < sidebar.index("[22 octobre 2026](Daily-2026-10-22)")
        dailys = (wiki / "Dailys.md").read_text()
        assert dailys.index("23 octobre 2026") < dailys.index("22 octobre 2026"), dailys

        assert module.sync(root, wiki, REPO, ENTRIES) == (0, 0), "second passage sans changement"
        (root / "ml").mkdir()
        (root / "ml" / "README.md").write_text("# ML\n")
        assert module.sync(root, wiki, REPO, ENTRIES)[0] == 2, "la page optionnelle apparaît (page et barre latérale)"
        assert "[ML](ML)" in (wiki / "_Sidebar.md").read_text()
    print("ok   sync-wiki : pages générées, Home et dailys conservés, obsolètes supprimées, idempotent")


test_links()
test_check()
test_sync()
