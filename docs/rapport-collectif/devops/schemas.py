"""Schémas de la partie DevOps du rapport collectif (PNG).

Lancement, depuis ce dossier : python schemas.py   (nécessite matplotlib)
Les schémas décrivent la chaîne d'intégration et de livraison ; les modifier ici, puis relancer.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# Palette sobre : un remplissage par famille, bordure sombre, texte noir
DEV = "#dbeafe"       # développement
CTRL = "#e5e7eb"      # contrôles
LIV = "#d1fae5"       # livraison
PROD = "#fde68a"      # production
STOP = "#fecaca"      # refus
EDGE = "#374151"
TEXT = "#111827"


def canvas(width, height):
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, fc=CTRL, size=10, bold_first=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=fc, ec=EDGE, lw=1.3))
    lines = text.split("\n")
    if bold_first and len(lines) > 1:
        ax.text(x + w / 2, y + h - 0.2, lines[0], ha="center", va="top", fontsize=size + 0.5,
                fontweight="bold", color=TEXT)
        ax.text(x + w / 2, y + h - 0.2 - 0.34, "\n".join(lines[1:]), ha="center", va="top",
                fontsize=size, color=TEXT, linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size,
                color=TEXT, linespacing=1.35)


def arrow(ax, start, end, label=None, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14, lw=1.4,
                                 color=EDGE, connectionstyle=f"arc3,rad={rad}", linestyle=ls))
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + 0.12, label, ha="center",
                va="bottom", fontsize=8.5, color=TEXT)


def save(fig, name):
    fig.savefig(name, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def cycle():
    fig, ax = canvas(13.5, 6.4)
    w, h = 2.3, 1.55
    xs = [0.2 + i * 2.65 for i in range(5)]
    top, bottom = 4.3, 1.5
    row1 = [
        ("1. Branche courte\nhooks locaux : commits,\nnom de branche, ruff", DEV),
        ("2. Pull request\ntitre, branche, commits\nconventionnels", DEV),
        ("3. Contrôles de la CI\ntests, sécurité, qualité\nrésumés par ci-ok", CTRL),
        ("4. Revue\nune approbation,\nfils résolus", CTRL),
        ("5. Fusion en squash\ndans main", CTRL),
    ]
    row2 = [
        ("6. Publication\ndes images sur GHCR\nsha-commit et main", LIV),
        ("7. Staging (VM)\nimages tirées toutes\nles 2 minutes", LIV),
        ("8. Recette\nsur le staging", LIV),
        ("9. Release manuelle\nversion vX.Y.Z,\nimages promues", PROD),
        ("10. Production (AWS)\napprobation, SSM,\ncontrôle de /health", PROD),
    ]
    for x, (t, c) in zip(xs, row1):
        box(ax, x, top, w, h, t, c)
    for x, (t, c) in zip(xs, row2):
        box(ax, x, bottom, w, h, t, c)
    for i in range(4):
        arrow(ax, (xs[i] + w + 0.02, top + h / 2), (xs[i + 1] - 0.02, top + h / 2))
        arrow(ax, (xs[i] + w + 0.02, bottom + h / 2), (xs[i + 1] - 0.02, bottom + h / 2))
    arrow(ax, (xs[4] + w / 2, top - 0.02), (xs[0] + w / 2, bottom + h + 0.02), rad=0.0)
    ax.text(10.6, 3.5, "main devient la source des images", ha="center", va="top", fontsize=9, color=TEXT)
    ax.text(0.2, 0.75, "Bleu : développement    Gris : contrôles    Vert : livraison    Jaune : production",
            fontsize=9, color=TEXT)
    ax.text(0.2, 0.3, "Le retour arrière redéploie un tag déjà publié, sans passer par les étapes 1 à 9.",
            fontsize=9, color=TEXT)
    save(fig, "cycle-modification.png")


def controles():
    fig, ax = canvas(13.5, 6.6)
    box(ax, 0.2, 2.75, 1.9, 1.1, "Pull request\nou push\nsur main", DEV)
    # groupes
    box(ax, 2.9, 4.65, 3.6, 1.5,
        "Forme\npr-title\nbranch-name\ncommit-messages", CTRL, bold_first=True)
    box(ax, 2.9, 2.2, 3.6, 2.1,
        "Tests des modules touchés\nchanges (tri des modules)\npython : ruff, pytest, couverture\nfrontend : tests et build\nmigrations : appliquées deux fois\nterraform : fmt et validate", CTRL, bold_first=True)
    box(ax, 2.9, 0.3, 3.6, 1.6,
        "Sécurité et qualité\nsecurity : Trivy (dépendances,\nsecrets, Terraform, Dockerfiles)\nsonar : couverture du code neuf", CTRL, bold_first=True)
    box(ax, 8.0, 2.6, 2.3, 1.4, "ci-ok\nrésume tous les\ncontrôles", CTRL, bold_first=True)
    box(ax, 11.0, 2.6, 2.3, 1.4, "Règle de main\nci-ok vert, branche\nà jour, 1 approbation", PROD, bold_first=True)
    for y in (5.4, 3.25, 1.1):
        arrow(ax, (2.12, 3.3), (2.88, y))
        arrow(ax, (6.52, y), (7.98, 3.3))
    arrow(ax, (10.32, 3.3), (10.98, 3.3))
    ax.text(0.2, 6.3, "Contrôles d'une pull request", fontsize=12, fontweight="bold", color=TEXT)
    ax.text(6.6, 0.1, "Sur un push de main, les contrôles de forme sont ignorés et tout est testé ; "
            "la publication des images suit ci-ok.", fontsize=9, color=TEXT)
    save(fig, "controles-pr.png")


def release():
    fig, ax = canvas(13.5, 9.4)
    cx, w, h = 1.0, 4.6, 0.95
    steps = [
        (8.2, "Lancement manuel de la release\nsha facultatif, recette confirmée", DEV),
        (6.85, "Le staging a-t-il annoncé ce commit ?", CTRL),
        (5.5, "La CI de ce commit est-elle verte ?", CTRL),
        (4.15, "feat ou fix depuis le dernier tag ?", CTRL),
        (2.8, "Version calculée, tag et release GitHub\nimages promues : tag vX.Y.Z, SBOM joints", LIV),
        (1.45, "Approbation de l'environnement production", PROD),
        (0.1, "Déploiement par SSM : sauvegarde de la base,\ncompose pull et up, contrôle de /health", PROD),
    ]
    for y, t, c in steps:
        box(ax, cx, y, w, h, t, c)
    for i in range(len(steps) - 1):
        arrow(ax, (cx + w / 2, steps[i][0] - 0.02), (cx + w / 2, steps[i + 1][0] + h + 0.02))
    for y in (6.85, 5.5, 4.15):
        box(ax, 7.2, y + 0.1, 2.7, 0.75, "Refus\navec message", STOP, size=9.5)
        arrow(ax, (cx + w + 0.02, y + h / 2), (7.18, y + h / 2), label="non")
    box(ax, 7.2, 1.2, 5.6, 1.5,
        "Retour arrière\nlancer « Déploiement en production »\navec un tag déjà publié", DEV, bold_first=True)
    arrow(ax, (7.18, 1.95), (cx + w + 0.02, 1.925), rad=0.0)
    ax.text(0.2, 9.4, "Release et retour arrière", fontsize=12, fontweight="bold", color=TEXT, va="top")
    ax.text(7.2, 0.5, "La production ne reçoit jamais une nouvelle construction :\nune image déjà recettée au staging est promue puis déployée.",
            fontsize=9, color=TEXT, va="center")
    save(fig, "release-et-retour-arriere.png")


def environnements():
    fig, ax = canvas(13.5, 6.4)
    zones = [
        (0.2, "Poste de\ndéveloppement", DEV,
         "docker compose\nhooks avant commit\ntests locaux"),
        (3.85, "GitHub", CTRL,
         "Actions : CI, release\nGHCR : images\nDeployments, Releases\nenvironnement\nproduction (approbation)"),
        (7.5, "Staging\nVM de l'école", LIV,
         "docker compose\nminuteur systemd (2 min)\nMLflow sur 127.0.0.1\nannonce le commit"),
        (11.15, "Production\nAWS eu-west-3", PROD,
         "CloudFront (HTTPS)\nEC2 : port 4000 seul\nSession Manager,\npas de SSH\nS3 chiffré"),
    ]
    w, ytop, ybot = 2.15, 5.6, 2.5
    for x, title, color, body in zones:
        ax.add_patch(FancyBboxPatch((x, ybot), w, ytop - ybot, boxstyle="round,pad=0.02,rounding_size=0.15",
                                    fc=color, ec=EDGE, lw=1.3))
        ax.text(x + w / 2, ytop - 0.2, title, ha="center", va="top", fontsize=10.5, fontweight="bold",
                color=TEXT, linespacing=1.3)
        ax.text(x + w / 2, ytop - 1.15, body, ha="center", va="top", fontsize=9, color=TEXT, linespacing=1.4)
    arrow(ax, (2.37, 4.1), (3.83, 4.1), label="push, PR")
    arrow(ax, (6.02, 4.1), (7.48, 4.1), label="images tirées")
    arrow(ax, (7.48, 3.1), (6.02, 3.1), label="annonce du commit")
    # GitHub vers AWS : trajet par le bas, sans croiser le staging
    gx, ax_x, y = 3.85 + w / 2, 11.15 + w / 2, 1.5
    ax.plot([gx, gx], [ybot - 0.02, y], color=EDGE, lw=1.4)
    ax.plot([gx, ax_x], [y, y], color=EDGE, lw=1.4)
    arrow(ax, (ax_x, y), (ax_x, ybot - 0.02))
    ax.text((gx + ax_x) / 2, y + 0.12, "jeton OIDC puis commande SSM (déploiement de la production)",
            ha="center", va="bottom", fontsize=9, color=TEXT)
    ax.text(0.2, 0.9, "Aucun secret AWS longue durée : le déploiement échange un jeton OIDC contre un rôle limité à une instance.",
            fontsize=9, color=TEXT)
    ax.text(0.2, 0.4, "Le staging et la production exécutent les mêmes images ; seuls l'environnement et les accès changent.",
            fontsize=9, color=TEXT)
    save(fig, "environnements.png")


if __name__ == "__main__":
    cycle()
    controles()
    release()
    environnements()
    print("ok")
