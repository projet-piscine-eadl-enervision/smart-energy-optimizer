# Rapport collectif

Brouillon commun du rapport collectif de management de projet (EC02), publié au wiki à chaque fusion. Le plan suit les attendus de l'épreuve : organisation de l'équipe, méthodologie, planning et risques, compte rendu d'activité honnête. Les annexes ne comptent pas dans les 10 pages.

- [Introduction : contexte et objectifs](contexte-et-objectifs.md)
- [1. Organisation de l'équipe](organisation.md)
- [2. Méthodologie](methode.md)
- [3. Planning, jalons et risques](planning-et-risques.md)
- [4. Compte rendu d'activité](compte-rendu.md), une page par domaine :
  - [5.1 DevOps](devops/README.md) (ticket #165)
  - [5.2 Cloud](cloud/README.md) (ticket #166)
  - [5.3 Données](donnees/README.md) (ticket #168)
  - [5.4 Produit et interface](produit-et-interface/README.md) (ticket #167)
  - [5.5 Backend et ML](backend-et-ml/README.md) (ticket #171)
  - [5.6 Tests](tests/README.md) (ticket #170)
- [Annexes](annexes.md)

## Écrire sa partie

- Modifier uniquement sa page ou son dossier, dans une PR courte. Chaque fichier commence par un seul titre de niveau 1.
- La page du domaine (`README.md` du dossier) tient en une page : livré, problèmes résolus, non livré et pourquoi, outils. Le détail par compétence de la grille d'auto-évaluation est dans `competences.md` du même dossier (annexe) : pour chaque compétence, des pistes et des preuves possibles sont données, à remplacer par le texte de l'auteur.
- Prose, sans tiret quadratin, peu de tableaux. Rien qui ne parle qu'à l'équipe (codes de travail, étapes internes) : le lecteur ne connaît pas notre historique.
- Une partie terminée perd sa ligne « En cours » et ses consignes. Les images se placent à côté de la page, avec un lien relatif.

## Assemblage final

Le rendu est un seul fichier, `EADL26_EC02 - Rapport Collectif READL_006-G3.md`, avec son PDF. Il est copié depuis ces pages, dans l'ordre du sommaire, sans ce sommaire, sans les consignes ni les parties restées « en cours », annexes à la suite. Les schémas sont des images placées à côté des pages : un fichier copié hors du dépôt les perd, il faut donc les intégrer au fichier final (en base64) ou produire le PDF depuis le dépôt.
