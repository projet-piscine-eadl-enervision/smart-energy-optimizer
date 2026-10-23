# Audit au 21/10/2026, suivi au 22/10/2026

Légende : **P1** à traiter avant tout, **P2** à traiter bientôt, **P3** confort ou nettoyage. Un point sans mention de statut est resté ouvert ; les autres portent **Traité**, **Écarté** ou **Laissé en l'état**, avec la date.

## Sécurité

- **P1. Publication d'images déclenchable depuis un fork.** `publish-images.yml` se déclenche sur `workflow_run` avec `branches: [main]`, filtre qui porte sur le nom de la branche d'origine. Une PR venant d'un fork dont la branche s'appelle `main` peut le déclencher. Le job vérifie seulement `conclusion == 'success'`, récupère le code de ce `head_sha`, dispose de `packages: write` et pousse l'image `:main`, que la VM de staging tire toutes les 2 minutes puis exécute. Le dépôt est public : un inconnu dont la CI passe pourrait faire tourner un conteneur sur la VM. À corriger : exiger `github.event.workflow_run.event == 'push'` et `github.event.workflow_run.head_repository.full_name == github.repository`. Le réglage « approbation des workflows des contributeurs externes » (Settings > Actions > General) réduit le risque sans le supprimer, car il ne vaut qu'à la première contribution d'une personne. **Traité le 22/10/2026** : les deux conditions sont dans le job `build`, et `:main` ne peut de toute façon plus être déplacé que par la tête de `main` (voir « Course sur l'image `:main` »). Reste à vérifier côté GitHub la politique d'approbation, au niveau `first_time_contributors` au dernier relevé.
- **P1. Politique de sécurité absente.** Aucun `SECURITY.md` n'existe. Il faut ajouter une politique de sécurité qui dit comment signaler une vulnérabilité (canal privé, délai de réponse, périmètre), et activer le signalement privé de vulnérabilités du dépôt (Settings > Security > Private vulnerability reporting). Documentation : <https://docs.github.com/fr/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/add-security-policy>. Le dépôt étant public, c'est aussi ce que GitHub affiche dans l'onglet Security. **Traité le 23/10/2026 pour le fichier** : `SECURITY.md` ajouté. Reste un réglage à faire dans GitHub (hors du code) : activer le signalement privé de vulnérabilités, ainsi que le secret scanning et sa protection au push, désactivés au dernier relevé.
- **P2. API sans authentification.** Le sujet demande une API sécurisée. Aujourd'hui `/docs` et `/health` sont ouverts, et `/health` publie le titre du commit et le sha, y compris en production. **Largement traité le 23/10/2026** (PR #102) : l'API a une authentification JWT, et `/history`, `/predictions`, `/recommendations` et `/auth/me` exigent le jeton. Restent ouverts par choix : `/docs`, `/health`, `/auth/login`. À trancher : `/auth/register` est ouvert à tous.
- **P2. Contrôle de release déclaratif.** La case « staging vérifié » de `release.yml` est une déclaration, rien ne vérifie que le staging affiche bien ce sha. Côté production, l'auto-approbation et le contournement par les administrateurs sont voulus, mais cela signifie que la personne qui tague peut aussi déployer seule. À présenter comme un choix assumé.
- **P3. Scan des images.** Trivy ne scanne que le système de fichiers, pas les images construites. Les actions tierces sont épinglées par tag, sauf Trivy et `configure-aws-credentials` qui le sont par sha.
- **P3. `.dockerignore`.** Ceux de `api` et du frontend n'excluent pas `.env`, contrairement à `etl` et `ml`. **Traité le 23/10/2026.**

Vérifié et sain : `assign-pr-author.yml` utilise `pull_request` (pas `pull_request_target`) ; les entrées de `release.yml` passent par `env:` ; le tag de `deploy-production.yml` est validé en `vX.Y.Z` avant d'être inséré dans le script exécuté sur l'instance ; la base n'est pas publiée sur le staging.

## CI et publication des images

- **P2. Course sur l'image `:main`.** `publish-images.yml` n'a pas de groupe de concurrence. Deux merges rapprochés peuvent se terminer dans le désordre et un commit plus ancien écrase `:main`, donc le staging. Ajouter un groupe `concurrency` sur le workflow. **Traité le 22/10/2026, autrement** : un groupe de concurrence remplace les runs en attente et aurait fait perdre leur image `sha-<commit>` à certains commits, ce dont la release et la production ont besoin. L'image `sha-<commit>` est donc toujours publiée, et `:main` n'avance que si ce commit est encore la tête de `main`. Limite connue : si un commit plus récent échoue en CI, `:main` reste en retard jusqu'au prochain commit vert.
- **P2. Annulation de la CI sur `main`.** `ci.yml` annule le run en cours à chaque nouveau push sur la même référence. Un merge rapide annule la CI du précédent : ce commit n'a jamais d'image et ne peut pas passer le contrôle « CI verte » de `release.yml`. Désactiver `cancel-in-progress` sur `main` (le garder pour les PR). **Traité le 22/10/2026** : chaque commit de `main` a son propre groupe de concurrence, car GitHub remplace aussi un run en attente par le suivant même sans annulation ; seules les PR annulent leur run précédent.
- **P2. Job Cypress incompatible.** Le job `e2e` lance `npm run preview` et attend le port 4173, ce qui est propre à Vite. Le script `preview` n'existe pas dans `frontend/package.json` : le job échouera le jour où un `cypress.config` apparaîtra. Le job est inactif sans `cypress.config.*` ; à réécrire pour Angular avec le premier test de bout en bout. **Port corrigé le 23/10/2026** (`npm start`, port 4200), mais le besoin du job est remis en cause : voir « Notes du 23/10/2026 ».
- **P3. Dépendances de test non figées.** Le job Python installe `ruff`, `pytest` et `pytest-cov` sans version dans `ci.yml`, et aucun fichier `requirements-dev` n'existe sur `main`. **Traité le 22/10/2026** : `requirements-dev.in` et `.txt` pour `api`, `etl` et `ml`, compilés par `infra/scripts/compile-requirements.sh` et installés par la CI.
- **Contrôles locaux avant commit et avant push.** Ajouté le 22/10/2026 : des hooks `pre-commit` (`.pre-commit-config.yaml`) reprennent les contrôles de la CI (messages de commit, nom de branche, `ruff`, clés privées, commit direct sur `main`). Le nom de branche est vérifié par un script commun à la CI et aux hooks. Procédure d'installation dans le README (étape 7). Ils ne remplacent pas la CI.

## Déploiement et exploitation

- **P2. Retour arrière du staging incohérent.** Avec `IMAGE_TAG` figé, `update-staging.sh` fait quand même `reset --hard origin/main` sur le fichier compose : d'anciennes images tournent avec un compose récent. En production le problème n'existe pas, le workflow faisant un checkout du tag. **Traité le 22/10/2026** : le script ramène le fichier compose au commit figé (`sha-<40 caractères>` ou tag `vX.Y.Z`) et laisse le reste du dépôt, scripts compris, sur `main`. Testé sur des dépôts jetables, pas encore sur la VM.
- **P2. Exposition.** Le staging publie l'API sur le port 8000 alors que le proxy `/api` du frontend la rend inutile en direct. À trancher : conserver l'accès direct pour la recette, ou le fermer. **Laissé en l'état le 22/10/2026** : le workflow `Release` et le guide de recette lisent le sha sur `:8000/health`, et la VM n'est joignable que depuis le réseau de l'école.
- **P3. Fichier compose.** `docker-compose.staging.yml` sert aussi de fichier de production : le nom induit en erreur (envisager `docker-compose.prod.yml` ou un nom neutre). **Écarté le 22/10/2026** : `deploy-production.yml` nomme le fichier en dur, un retour arrière vers un ancien tag échouerait après un renommage.
- **P3. Supervision.** Aucune image n'a de `HEALTHCHECK` et le compose n'en définit pas pour `api`. Aucune alerte si le minuteur de mise à jour échoue. **Partiellement traité le 23/10/2026** : `HEALTHCHECK` ajouté aux images `api`, `etl` et `frontend` (pas `ml`, qui n'est pas un service). Aucune alerte sur le minuteur pour l'instant.

## Tests

- **P1. Aucun test sur `main`.** Les trois dossiers `tests/` (`api`, `etl`, `ml`) ne contiennent qu'un `.gitkeep`, et le job pytest tolère « aucun test collecté ». Seul `app.spec.ts` existe côté frontend.
- **P2. Travail non versionné.** Les tests d'architecture du frontend, les tests de l'ETL (écrits, jamais exécutés) et `suivi.md` sont encore dans des stashes locaux. Les remettre sur des branches pour qu'ils existent dans le dépôt.
- **À prévoir** : une cible de couverture explicite (le dossier de conception en annonçait une) et un seuil dans la CI, sinon le jury verra des chiffres sans engagement.

## API, ETL et ML

- **P2. Aucun pilote de base dans l'API.** `DATABASE_URL` est passée à l'API, mais `api/requirements.in` ne contient ni `psycopg` ni `sqlalchemy` : elle ne peut pas se connecter à la base.
- **P2. Divergence entre l'API et l'ETL.** L'API accepte l'absence d'identifiants du mock (URL interne de l'école) et normalise l'URL. L'ETL lève une `RuntimeError` non gérée (erreur 500), n'a pas d'URL par défaut ni de `rstrip`. C'est la cause du contournement `-` dans `staging.env` : aligner l'ETL sur l'API.
- **P3. Nom du paquet de l'ETL.** Le dossier `etl/api_mock` suggérait une simulation de l'API Mock alors qu'il contient le client. **Traité le 23/10/2026** : renommé `etl/mock_client`.
- **Normal à ce stade, à suivre** : l'ETL n'écrit pas encore dans TimescaleDB (ni schéma, ni hypertable, ni migrations, ni modèle `EnergyReading`) ; le ML se limite à un `SELECT 1` et à un run MLflow de vérification ; il n'existe ni détection de pics, ni recommandations, ni tableau de bord.

## Nettoyage du dépôt

Tout ce qui suit est **traité le 22/10/2026**.

- `.release-please-manifest.json` et `CHANGELOG.md` étaient figés à 1.0.2 alors que les tags allaient jusqu'à v1.7.0 : supprimés, les notes de version viennent des GitHub Releases.
- L'exception `release-please--*` dans le contrôle des noms de branche (`ci.yml`) ne servait plus : retirée.
- `.env.example` contenait deux fois le bloc `ETL_PORT` : doublon retiré.
- Des `.gitkeep` subsistaient à côté de vrais fichiers (`docs/`, `infra/scripts/`) : supprimés.
- `frontend/.prettierrc.json` n'était jamais lu, `frontend/.prettierrc` étant prioritaire : supprimé.

## Notes du 23/10/2026 (à reprendre)

- **L'image `etl` de `main` plante au démarrage.** Le commit `74a47de` (#121) a remplacé `import httpx` par `import httpx2` dans `etl/api_mock/routers/sites.py` et `services/site_service.py`, sans toucher à `etl/requirements.in` (`httpx`) ni à `requirements.txt` (`httpx==0.28.1`). Reproduit en lançant l'image : `ModuleNotFoundError: No module named 'httpx2'`. La CI ne le voit pas (`ruff` n'importe pas les modules, `etl/tests/` est vide). Deux issues : revenir à `httpx` dans l'ETL, ou passer l'ETL à `httpx2` avec ses dépendances. Le choix de `httpx2` dans l'API reste à justifier (paquet publié sur PyPI depuis mai 2026, mainteneur non vérifié). À traiter avec le rebase de la PR #97, qui utilise `httpx`.
- **L'ETL devrait avoir un `/health`**, indépendant du mock, comme l'API (avec un `/health/mock` séparé si besoin). La sonde Docker de l'ETL utilise `/openapi.json` en attendant : à remplacer par `/health` une fois la route ajoutée.
- **Sondes Docker non observées à l'état `healthy`.** Les trois images se construisent et la sonde est enregistrée, mais l'image `api` seule s'arrête faute de `DATABASE_URL` et `SECRET_KEY` (sans valeur par défaut dans `app/core/config.py`). À vérifier avec la pile complète : `docker compose up -d` puis `docker ps`.
- **Job Cypress probablement inutile.** Le front teste avec Vitest (`ng test`), `package.json` ne contient aucune dépendance Cypress et `frontend/cypress/` ne contient qu'un `.gitkeep`. À décider : supprimer le job `e2e`, son entrée dans `needs` de `ci-ok` et la mention dans `CONTRIBUTING.md`, ou introduire un outil de bout en bout (Cypress ou Playwright) le jour où un test est prévu.
- **Nom du paquet `etl/api_mock`.** Il contient le client de l'API Mock (routers, services, schémas, config), pas une simulation : le nom prête à confusion. À renommer en `client` ou `sources` après la fusion de la PR #97, qui ajoute des fichiers dans ce dossier (conflit sinon).
- **`/auth/register` est ouvert à tous.** À trancher : inscription libre voulue, ou réservée à un rôle.
- **Réglages GitHub à activer par un propriétaire** (hors du code) : signalement privé de vulnérabilités (désactivé au 23/10), secret scanning et protection au push (désactivés), politique d'approbation des workflows externes (`first_time_contributors`).
- **Scan Trivy des images** (P3) : non traité, à faire dans une PR séparée car il modifie le workflow de publication.
