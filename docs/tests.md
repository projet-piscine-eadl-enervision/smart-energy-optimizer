# Tests

Cette page décrit les tests du projet : ce qui existe, comment les lancer en local, ce que la CI en fait, et les règles à suivre pour en ajouter. Les contrôles de qualité et de sécurité (Trivy, SonarQube, OWASP ZAP) sont détaillés dans [Qualité et sécurité de la CI](qualite-et-securite-ci.md).

## Vue d'ensemble

| Suite | Où | Outil | Ce qu'elle vérifie | En CI |
|---|---|---|---|---|
| API | `api/tests/` | pytest | routes, authentification, droits par site, anti-bruteforce, schémas, requêtes SQL | job `python (api)` |
| ETL | `etl/tests/` | pytest | client du mock, nettoyage, collecte, backfill, chargements en base, métriques | job `python (etl)` |
| ML | `ml/tests/` | pytest | features, modèles, évaluation, pipeline MLflow, suivi de dérive, recommandations | job `python (ml)` |
| Frontend | `frontend/src/**/*.spec.ts` | Vitest (`ng test`) | services, garde, intercepteur, pages, proxy SSR | job `frontend` |
| Bout en bout | `frontend/cypress/e2e/` | Cypress | parcours utilisateur sur la vraie pile | job `e2e` |
| Charge | `infra/k6/` | k6 | latence et erreurs des routes du tableau de bord | job `load` |
| Scripts d'infra | `infra/scripts/test-*` | bash, Python | tri des modules, staging, couverture Sonar, rapport ZAP, wiki | jobs `changes` et `Wiki` |
| Alertes | `monitoring/prometheus/alerts.test.yml` | promtool | déclenchement des règles d'alerte | job `monitoring` |
| Migrations | `db/migrations/` | migrate | migrations appliquées deux fois sur une base vide | job `migrations` |

Ordre de grandeur au 28/10/2026 : environ 135 tests pour l'API, 140 pour l'ETL, 85 pour le ML, 105 pour le frontend et 26 scénarios Cypress.

## Tout lancer en une commande

Depuis WSL, à la racine du clone :

```bash
./infra/scripts/test-all.sh               # lint, tests et couverture de api, etl, ml puis frontend
./infra/scripts/test-all.sh etl frontend  # seulement ces modules, dans cet ordre
```

Le script fait la même chose que la CI : `ruff check` puis `pytest --cov` pour chaque module Python, ESLint, Prettier puis `ng test --coverage` pour le frontend. Il s'arrête à la première erreur et finit par un récapitulatif (résultat et couverture par module).

- **Python** : un environnement par module dans `.venv-tests/<module>` (les versions figées diffèrent d'un module à l'autre). Il est créé au premier lancement, puis réinstallé seulement si `requirements.txt` ou `requirements-dev.txt` change. Python 3.13 est requis, comme en CI (`PYTHON=/chemin/vers/python3.13` pour en choisir un autre).
- **Frontend** : avec Node 24 dans WSL, tout tourne en local. Sinon, les tests passent dans le conteneur `frontend`, sans rien installer.
- **Base de données** : les tests qui touchent la base sont ignorés sans `DATABASE_URL`. Pour les inclure, sur la base de dev migrée :

```bash
docker compose up -d db && docker compose run --rm migrate
DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision ./infra/scripts/test-all.sh etl ml
```

- **Rapports de couverture** : `<module>/coverage.xml` (Python) et `frontend/coverage/enervision/` (lcov et HTML).

## Tests Python (API, ETL, ML)

### Lancer un module

Depuis le dossier du module, environnement activé (`pip install -r requirements.txt -r requirements-dev.txt`) :

```bash
python -m pytest                      # tous les tests du module
python -m pytest tests/test_auth.py   # un fichier
python -m pytest -k throttle          # les tests dont le nom contient « throttle »
python -m pytest --cov=. --cov-report=term-missing   # avec la couverture, comme la CI
ruff check .                          # lint, à lancer aussi avant de pousser
```

Chaque module a un `pytest.ini` qui ajoute le dossier du module au chemin d'import (`pythonpath = .`) et limite la recherche à `tests/`. Les outils sont figés dans `requirements-dev.txt` (`pytest`, `pytest-cov`, `coverage`, `ruff`) : une nouvelle version ne casse pas la CI sans changement de code.

### Deux familles de tests

**Tests unitaires** (la grande majorité) : ni réseau ni base, moins d'une seconde par module.

- **API** (`api/tests/conftest.py`) : les variables obligatoires (`DATABASE_URL`, `SECRET_KEY`, `MOCK_API_URL`) reçoivent des valeurs de test avant l'import de l'application. La session SQLAlchemy est remplacée par une `FakeSession` en mémoire, l'anti-bruteforce par un `MemoryFailureStore`, et l'heure par une `Clock` que le test fait avancer (`clock.advance(minutes=15)`). Le `TestClient` est créé sans bloc `with`, donc le démarrage de l'application ne touche pas la base.
- **ETL** (`etl/tests/conftest.py`) : l'API Mock est remplacée par un `httpx2.MockTransport` (fixture `mock_api`), qui répond avec une fonction du test et garde les requêtes reçues pour vérifier l'URL et l'authentification. Les fonctions async sont testées avec le plugin d'anyio (`@pytest.mark.anyio`).
- **ML** (`ml/tests/conftest.py`) : données horaires factices (`make_hourly`) et données qui imitent le mock (`make_mock_like` : profil fixe et bruit de 5 %). Les tests du pipeline utilisent un MLflow en SQLite dans un dossier temporaire (`tmp_path`).

**Tests d'intégration** (fichiers `*_db.py`) : ils tournent sur une vraie base TimescaleDB migrée par `db/migrations`. Ils sont **ignorés sans base**, grâce à un `pytestmark = pytest.mark.skipif(...)` en tête de fichier. La CI démarre une base migrée et fournit `DATABASE_URL`, ils y tournent donc toujours. Chaque test nettoie derrière lui : transaction annulée à la fin (`connection.transaction(force_rollback=True)`), ou création puis suppression de sites réservés aux tests (`SITE990`, `SITE997`…), qui ne gênent pas les vrais sites.

**Tests sur les vrais fichiers** (ETL, `*_real_data.py`) : ils lisent le jeu de données suivi par DVC et sont ignorés tant que `dvc pull` n'a pas été fait (voir [Données et DVC](donnees-dvc.md)).

### Ce que chaque module couvre

- **API** : santé, inscription et connexion, JWT, rôles et accès par site (`test_site_access.py`), anti-bruteforce du login (en mémoire et en base), routes de données (`/sites`, `/history`, `/predictions`, `/recommendations`, `/alerts`), schémas, configuration, documentation OpenAPI (fermée en production, chaque champ décrit).
- **ETL** : client et schémas du mock, collecte des mesures courantes, backfill, nettoyage de l'historique (règles et refus des chemins hors des dossiers prévus), chargements en base (référentiel, historique), battement des capteurs, métriques Prometheus, point d'entrée du pipeline.
- **ML** : features (dont `test_no_future_leakage`, qui vérifie qu'aucune variable ne voit l'avenir), modèles et comparaison au naïf, évaluation, entraînement, promotion et prédiction de bout en bout avec MLflow, suivi de la dérive, détection d'anomalies, recommandations, requêtes SQL du module.

## Tests unitaires du frontend

Vitest, lancé par le builder Angular `@angular/build:unit-test`, dans jsdom. Chaque fichier `*.spec.ts` est à côté du fichier qu'il teste.

```bash
cd frontend
npx ng test --watch=false                       # une passe, comme en CI
npx ng test --watch=false --coverage            # avec la couverture
npm run lint && npm run format:check            # ESLint et Prettier, exigés par la CI
```

Sans Node 24 dans WSL, depuis la racine : `docker compose run --rm --no-deps -T -e CI=true frontend npx --no-install ng test --watch=false`, ou simplement `./infra/scripts/test-all.sh frontend`.

**Principe** : les écrans sont testés avec les vrais services et le vrai `HttpClient` d'Angular, seul le réseau est simulé. Les tests vérifient donc les chemins et les paramètres réellement envoyés à l'API. Les outils sont dans `src/app/testing/api.ts` :

- `apiProviders()` : fournit `HttpClient` et sa version de test ;
- `answer({ '/api/sites': SITES, '/api/alerts': new Failure(500) })` : répond à toutes les requêtes en attente selon leur chemin, et renvoie les URL vues avec leurs paramètres. Une requête non prévue fait échouer le test.

Pour un service seul, `HttpTestingController.expectOne(...)` puis `httpMock.verify()` dans `afterEach` (exemple : `core/energy.service.spec.ts`).

Couverture : services (`auth`, `energy`, `sites`, `alerts`), garde et intercepteur, composants partagés (`shell`, `site-select`), toutes les pages (connexion, tableau de bord, sites, détail d'un site, alertes, pics) et le proxy `/api` du serveur SSR.

## Tests de bout en bout (Cypress)

Les scénarios tournent contre la vraie pile (frontend, API, base migrée), dans le conteneur `e2e` (image `cypress/included`, navigateur Chrome). Il n'y a ni Node ni Cypress à installer dans WSL.

```bash
docker compose up -d
docker compose --profile e2e run --rm e2e                                       # tous les scénarios
docker compose --profile e2e run --rm e2e --browser chrome --spec e2e/login.cy.js  # un seul fichier
```

En cas d'échec, une capture d'écran est écrite dans `frontend/cypress/screenshots/` (ignoré par Git). En CI, elle est jointe au run (artefact `cypress-screenshots`), avec les journaux de la pile.

| Fichier | Parcours |
|---|---|
| `login.cy.js` | formulaire, connexion, mauvais mot de passe, email inconnu, API injoignable, déconnexion |
| `register.cy.js` | inscription, connexion directe, email déjà utilisé, contrôle du mot de passe |
| `auth-guard.cy.js` | redirections du garde, jeton refusé par l'API, aucune route protégée appelée sans jeton |
| `dashboard.cy.js` | compte sans site, états vides, recommandations et graphiques, erreur d'une route |
| `navigation.cy.js` | passage d'une page à l'autre, sites et détail, alertes et badge, pics prévus, filtre par site, user limité à son site |

**Données** : chaque test crée son propre compte par l'API, avec un email unique (`uniqueEmail()`), donc la base n'a jamais besoin d'être vidée. Un compte créé par l'API est un `user` sans site : les scénarios des écrans de données simulent le profil (`cy.stubAccount`, constantes `ADMIN` et `USER_SITE001`) et les données (`cy.intercept`), car la pile de test ne collecte rien.

**Commandes partagées** (`cypress/support/e2e.js`) : `createUser`, `getToken`, `visitAsLoggedIn`, `stubAccount`, `loginAsNewUser`, `submitAuthForm`. Les constantes et fonctions sont dans `cypress/support/helpers.js` : un scénario importe `helpers.js`, jamais `e2e.js` (les commandes seraient enregistrées deux fois).

En CI (`e2e`), le frontend est l'image de production (`docker-compose.e2e.yml`) : le serveur de dev Angular, lancé à froid, ne répond pas assez vite.

## Test de charge (k6)

Le scénario `infra/k6/smoke.js` simule 5 utilisateurs pendant une minute sur les routes du tableau de bord (`/sites`, `/history`, `/predictions`, `/recommendations`, `/alerts`). Il échoue (code 99) si une requête est en erreur ou si la p95 dépasse 500 ms, au global ou pour une route.

```bash
docker compose up -d api
# Dans le .env : K6_EMAIL et K6_PASSWORD d'un compte de test admin (jamais versionnés)
docker compose --profile load run --rm k6
docker compose --profile load run --rm -e VUS=20 -e DURATION=5m -e P95_MS=800 k6   # réglages
```

- **Garde-fou** (`infra/k6/lib.js`) : le script refuse une cible `*.cloudfront.net` ou `*.amazonaws.com`, et une API dont `/health` annonce `production`. On ne charge jamais la production, et on prévient l'équipe avant de charger le staging.
- **En CI** (`load`) : pile éphémère à base vide. Le job repère une route cassée ou une régression nette de latence, il ne mesure pas la capacité. Une seconde passe avec un seuil impossible (`P95_MS=1`) vérifie que k6 échoue bien : sans elle, un seuil mal écrit ne protégerait rien.
- **Pas encore fait** (#226) : scénarios de charge nominale, de saturation, de pic soudain et de login, à lancer à la main sur une base remplie.

## Tests des scripts d'infra et de la supervision

- `infra/scripts/test-changed-modules.sh` : vérifie, sur un dépôt Git jetable, quels modules la CI teste selon les fichiers modifiés.
- `test-staging-deployment.sh`, `test-report-staging-deployment.sh` : scripts de mise à jour du staging.
- `test-prefix-coverage.py`, `test-check-zap-report.py`, `test-sync-wiki.py` : préparation de la couverture pour Sonar, blocage sur les alertes ZAP hautes, synchronisation du wiki.
- `monitoring/prometheus/alerts.test.yml` : chaque règle d'alerte est testée avec des séries simulées (`promtool test rules alerts.test.yml`, depuis `monitoring/prometheus/`).

Ils sont lancés par le job `changes` de la CI, sauf `test-sync-wiki.py`, lancé par le workflow `Wiki` quand la documentation change, et les tests d'alertes, lancés par le job `monitoring`.

## Dans la CI

La CI ne teste que les modules touchés par la PR (`infra/scripts/changed-modules.sh`) :

| Fichiers modifiés | Jobs de test lancés |
|---|---|
| `api/` | `python (api)`, `e2e`, `dast`, `load` |
| `etl/`, `ml/` | `python (etl)`, `python (ml)` |
| `frontend/` | `frontend`, `e2e` |
| `db/` | `migrations`, et les tests Python de l'API, de l'ETL et du ML (ils tournent sur le schéma) |
| `infra/k6/` | jobs de l'API, dont `load` |
| `.github/`, `infra/scripts/`, fichiers compose, hooks | tout |

Sur un push de `main`, tout est testé. Le code 5 de pytest (aucun test collecté) est toléré.

**Couverture** : chaque job envoie son rapport à SonarQube Cloud, dont la porte de qualité exige **80 % de couverture sur le code neuf** de la PR. Sous ce seuil, le job `sonar` échoue : les lignes non couvertes sont listées dans l'onglet *Code* de la PR sur SonarCloud.

Le seul contrôle exigé pour fusionner dans `main` est `ci-ok`, qui résume tous les jobs.

## Ajouter des tests : conventions

### Règles communes

- **Un test par comportement**, nommé d'après ce qu'il vérifie. Identifiants en **anglais** (fonctions, variables, fixtures) ; docstrings, commentaires et messages restent en français, comme le reste du code.
- **Un test doit pouvoir échouer.** Avant de pousser un nouveau test, casser volontairement le code testé et vérifier qu'il passe au rouge.
- **Un correctif de bug arrive avec le test qui le reproduit.**
- **Pas de réseau ni de service externe** dans un test unitaire : on simule à la frontière (HTTP, base, horloge), jamais la fonction testée elle-même.
- **Pas de dépendance à l'ordre ni aux données existantes** : chaque test crée ce qu'il lit et nettoie ce qu'il écrit.
- **Aucun secret réel** : valeurs de test dans le `conftest.py` ou le `.env` local, jamais dans Git.
- On ne désactive jamais un test pour faire passer la CI. Un test instable est corrigé, ou signalé dans un ticket.
- Avant de pousser : `./infra/scripts/test-all.sh <modules touchés>`. Le hook pre-commit lance déjà `ruff`, ESLint et Prettier.

### Python

- Fichier `tests/test_<module>.py` à côté des autres, fonction `test_<behaviour>()`, par exemple `test_load_is_idempotent_and_never_stores_nan`.
- Réutiliser les fixtures du `conftest.py` du module (`client`, `db`, `make_user`, `auth_headers`, `user_headers`, `clock`, `mock_api`, `hourly`…) avant d'en créer une. Une fixture utile à plusieurs fichiers va dans `conftest.py`.
- Variables d'environnement : `monkeypatch.setenv` / `monkeypatch.delenv`, jamais `os.environ` modifié à la main dans un test.
- Fichiers : `tmp_path`, jamais un chemin du dépôt.
- Cas proches : `@pytest.mark.parametrize` plutôt qu'une boucle dans le test.
- **Test qui touche la base** : fichier séparé `test_<module>_db.py`, avec en tête le `pytestmark = pytest.mark.skipif(...)` du module (sur `DATABASE_URL` absente pour l'ETL et le ML, sur l'adresse de test du `conftest.py` pour l'API). Utiliser un identifiant de site réservé aux tests et annuler la transaction, ou supprimer ce qui a été créé. Rappeler en docstring comment le lancer en local.
- Pour l'API, tester les droits : un admin voit tout (`auth_headers`), un user ne voit que son site (`user_headers`), un visiteur reçoit 401.

### Frontend

- `<name>.spec.ts` à côté de `<name>.ts`, `describe('<ClassName>')`, puis des `it('…')` qui décrivent le comportement en une phrase.
- Pages : `apiProviders()` et `answer({...})` de `src/app/testing/api.ts`, avec les vrais services. Tester aussi l'erreur d'une route (`new Failure(500)`).
- Services : `HttpTestingController`, `expectOne(...)` sur le chemin et les paramètres, et `httpMock.verify()` dans `afterEach`.
- `src/app/testing/` est réservé aux tests (règle ESLint) : rien du code de l'application ne doit l'importer.

### Cypress

- Un fichier `<parcours>.cy.js` par parcours dans `cypress/e2e/`, `describe` et `it` en français, comme les existants.
- Un compte neuf par test (`cy.loginAsNewUser(path, account)` ou `cy.createUser(uniqueEmail())`), jamais un compte partagé.
- Cibler les éléments par leur rôle ou leur attribut (`formcontrolname`, `type="submit"`), pas par une classe CSS de mise en forme.
- Pas de `cy.wait(<millisecondes>)` : attendre un élément ou une requête interceptée.
- Réserver Cypress aux parcours qui traversent plusieurs couches. Une règle d'affichage se teste plus vite en unitaire.

### k6

- Un nouveau scénario réutilise `guardTarget()` et `login()` de `lib.js` : le garde-fou de production n'est pas optionnel.
- Seuils déclarés dans `options.thresholds`, avec une ligne par route (`name:<route>`) pour savoir laquelle ralentit.
- Comptes et mots de passe uniquement par variables d'environnement (`K6_EMAIL`, `K6_PASSWORD`).

## Quand un test échoue

| Symptôme | Cause probable | Que faire |
|---|---|---|
| `test-all.sh` : « Python 3.13 introuvable » | autre version dans WSL | installer 3.13 ou passer `PYTHON=/chemin/vers/python3.13` |
| Tests `*_db.py` notés « skipped » | `DATABASE_URL` absente | normal en local ; la CI les lance. Pour les lancer : base de dev migrée et `DATABASE_URL` |
| Tests `*_real_data.py` ignorés | fichier DVC absent | `dvc pull` dans `etl/` |
| `ruff` refuse un cache dans `ml/.ruff_cache` | dossier créé par un conteneur (root) | `test-all.sh` met son cache dans `.venv-tests` ; sinon supprimer le dossier |
| Frontend : `Requête inattendue : /api/...` | la page appelle une route que le test n'a pas prévue | ajouter la route dans `answer({...})`, ou corriger l'appel |
| Cypress : la page ne se charge pas | pile non démarrée ou front encore en compilation | `docker compose ps`, attendre `http://localhost:4000/api/health` |
| Cypress : capture d'écran impossible | dossier `cypress/` non inscriptible pour l'utilisateur `node` | `chmod -R a+w frontend/cypress` |
| k6 : « API injoignable » | l'API redémarre (`.env` modifié) | relancer ; le script attend déjà une minute |
| k6 : 401 puis 429 | mauvais compte de test, puis blocage anti-bruteforce après 5 échecs | vérifier `K6_EMAIL` et `K6_PASSWORD` (et `unset` les anciennes valeurs du shell), attendre la fin du blocage |
| `sonar` : couverture du code neuf sous 80 % | lignes ajoutées sans test | compléter les tests des fichiers listés par SonarCloud |
