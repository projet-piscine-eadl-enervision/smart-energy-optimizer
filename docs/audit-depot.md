# Audit du dépôt, état au 26/10/2026

Base : `main` à `fe0793b` (PR #191, #192 et #194 incluses). Tests et couverture lus dans le journal de la CI de ce commit ; `pip-audit`, `npm audit` et Trivy relancés sur ce commit le 26/10 ; réglages GitHub lus par l'API le 26/10. Sauf mesure du 26/10, les lignes de *Traité* et *Assumé* sont reprises de l'audit du 24/10. Non vérifié : l'instance de production et son `production.env`, l'état réel de Terraform.

Légende : **P1** avant tout, **P2** bientôt, **P3** confort.

## Ouvert

### P1

Aucun.

### P2

- **Les rôles de la base ne sont pas utilisés** (#145). `api`, `etl`, le collecteur et `ml` se connectent avec `${POSTGRES_USER}`, le super-utilisateur (`docker-compose.staging.yml:47,65,83,137`). Les rôles `enervision_api`, `enervision_etl` et `enervision_ml` existent sans droit de connexion ; les droits de `enervision_ml` sont testés par `SET ROLE`. Créer les comptes de connexion et les donner aux services. Le rafraîchissement de `analytics.energy_hourly` demande un rôle propriétaire de cet agrégat.
- **Purge de `raw` non écrite.** Le schéma l'autorise (clé étrangère `ON DELETE SET NULL`, droit `DELETE` de l'ETL sur `raw`), mais aucune tâche ne purge : `raw` grossit d'environ 13 000 réponses par jour avec le collecteur.
- **État des alertes non calculé.** `last_seen_at` et `resolved_at` existent, rien ne les remplit : toutes les alertes paraissent actives.
- **Pas de monitoring ni d'alerte** (#150). Seules les sondes de santé existent : aucune alerte si le minuteur du staging ou le collecteur s'arrête. La release refuse seulement un commit que le staging n'a pas annoncé.
- **Pas de scan DAST ni de test de charge** (#149).
- **`/health` publie le titre du commit et le sha**, y compris en production (le workflow de déploiement s'en sert). À assumer ou à réduire.
- **`/auth/register` ouvert à tous, `/auth/login` sans limite d'essais** (aucun limiteur de débit dans l'API). À trancher : inscription fermée ou limitation.
- **Retour arrière du staging** : corrigé dans le script, testé seulement sur des dépôts jetables. À essayer sur la VM.

### P3

- **Une approbation survit aux pushs suivants.** La règle `main` a `dismiss_stale_reviews_on_push` et `require_last_push_approval` désactivés, et ne couvre pas les PR qui visent une autre branche que `main` : le code fusionné n'est donc pas forcément celui qui a été relu.
- **VM de staging : SSH de `root` et par mot de passe acceptés** (`sshd -T` le 26/10). Machine de l'école, joignable depuis son seul réseau ; restreindre à la clé seule si elle sert au-delà de la démonstration.
- **Tous les membres de l'équipe ont `AdministratorAccess` sur le compte AWS** (groupe `developpeurs` d'IAM Identity Center, MFA obligatoire ; décrit dans `infra/README.md`, non remesuré le 26/10). Pas de moindre privilège entre les personnes : choix de commodité pour un projet de deux semaines.
- **Énumération de comptes à l'inscription** : `/auth/register` répond 409 sur un e-mail connu, lié à la décision sur l'inscription ouverte.
- **`/health/mock` est public** et déclenche un appel sortant vers le mock à chaque requête.
- **Pas de linter pour le frontend** (#148) : `npm run lint --if-present` réussit faute de script `lint`.
- **Tests de bout en bout non branchés en CI.** Les quatre fichiers de tests Cypress (`frontend/cypress`) se lancent en local avec `docker compose --profile e2e run --rm e2e` ; aucun job de CI ne les exécute.
- **Couverture** : pas de seuil global dans la CI, et `pytest || [ $? -eq 5 ]` (`ci.yml:136`) tolère encore « aucun test collecté » alors que chaque module a des tests. La porte de SonarQube Cloud (80 % sur le code neuf) tient : 90,1 % le 26/10.
- **Pas de `terraform plan` en lecture seule en CI** : le job `terraform` ne lance que `fmt -check` et `validate`.
- **Compose de développement : MLflow (5000, sans authentification), l'ETL (8001) et l'API publiés sur toutes les interfaces** ; seul PostgreSQL est lié à `127.0.0.1`. Lier au moins MLflow à `127.0.0.1`, comme dans le compose du staging.
- **Trivy sur les images : rapport seul** (onglet Security, 2 alertes hautes ouvertes sur `db`) ; le blocage à la publication viendra une fois les alertes assumées en `.trivyignore` (#146). Les actions sont épinglées par tag, sauf Trivy, SonarQube et `configure-aws-credentials` (sha).
- **Longueur de `SECRET_KEY` non imposée** : `PyJWT` avertit sous 32 octets, mais l'API démarre quand même. 64 caractères en staging (vérifié le 26/10) ; la production est à vérifier.

## Traité

- **Revue et protection de `main`** (règle `main`, vérifiée par l'API le 26/10) : une approbation obligatoire, résolution des fils, `ci-ok` requis et branche à jour, fusion par *squash* uniquement, ni suppression ni force push. Aucun administrateur ne contourne la règle ; seule l'App `enervision-release` le peut, par PR. Les 21 dernières PR fusionnées dans `main` ont au moins une approbation.
- **Réglages GitHub** ([détail](reglages-github.md)) : signalement privé de vulnérabilités, alertes Dependabot, mises à jour de sécurité, secret scanning et protection au push activés (0 alerte de secret) ; approbation des workflows de tous les contributeurs externes ; Actions en lecture seule par défaut, sans création ni approbation de PR ; environnement `production` avec approbation, `staging` limité à `main`.
- **Dépendances** : `pip-audit` ne trouve rien sur `api`, `etl` et `ml` ; `npm audit` : 0 alerte sur les dépendances de production du frontend. Aucun fichier `.env`, `tfvars`, `backend.hcl`, clé ni `tfstate` suivi ou ajouté dans l'historique, aucun motif de clé dans les fichiers suivis.
- **Tests sur `main`** (journal de la CI de `fe0793b`) : API 63 tests (couverture 99 %), ETL 125 (99 %), ML 40 (99 %), frontend 32 cas Vitest (comptage des `it`, job `frontend` vert). Les tests d'intégration de l'ETL et du ML tournent sur une base TimescaleDB migrée (#192) : seuls 5 tests de l'ETL restent ignorés, faute du fichier DVC. Les requêtes SQL du ML sont testées avec le rôle `enervision_ml`.
- **CI** : jobs limités aux modules touchés, images réutilisées quand le dossier du module est inchangé, analyse SonarQube Cloud avec couverture, contrôle `terraform fmt` et `validate`, scan Trivy des dépendances et de la configuration. `publish` ne tourne que sur un push de `main` (plus de déclencheur `workflow_run`) ; sa condition porte `always()` pour que les contrôles propres aux PR, ignorés sur un push, ne le bloquent pas.
- **Release vérifiée** : la VM annonce à GitHub le commit qu'elle fait tourner, la release refuse un commit non annoncé ou sans `feat` ni `fix` depuis le dernier tag, puis enchaîne promotion (SBOM joints) et production dans un seul run.
- **Dependabot** : `pip`, `npm`, `docker` et Actions, une PR groupée par type le lundi ; `typescript` et `@types/node` ignorés (Angular fixe la plage de TypeScript), job `commit-messages` exclu pour le robot.
- **Wiki** : la documentation est publiée à chaque fusion sur `main` ; le job de PR n'a que la lecture, la publication n'a l'écriture que sur un push.
- **Données et base** : seize migrations rejouées deux fois en CI. Schéma prêt pour la purge de `raw`, l'état des alertes et l'historique étiqueté (table vide tant que son chargeur n'est pas fusionné) ; suivi du modèle en SQL en place (modèles, métriques, seuils, champion actuel). L'ETL se connecte à la base, charge les sites, collecte toutes les minutes (service `collector`, sonde Docker) et rattrape l'historique du mock par pas d'une heure (`backfill`, #194). Vérifié sur la VM : migrations, droits, collecteur sans doublon et rattrapage.
- **Module ML sur le staging** : MLflow (profil `mlflow`, lié à `127.0.0.1`, accès par tunnel SSH) et service `ml` à la demande (profil `ml-job`) ; `seed_dev.py` refuse de tourner hors développement ; garde-fou de fraîcheur (pas de prévision sur des mesures de plus de 3 h) et fin du jeu figée par `ML_DATA_END`.
- **API authentifiée** : JWT sur `/history`, `/predictions`, `/recommendations`, `/auth/me`. `python-jose` remplacé par `PyJWT` ; `/docs`, `/redoc` et `/openapi.json` fermés en production ; mot de passe de plus de 72 octets refusé (422 et 401, pas 500) ; connexion à durée égale pour un compte inconnu ; CORS limité à l'origine du frontend (revérifié à cette base, avec le test d'accès sans jeton des routes de données).
- **Images** : les cinq Dockerfiles finissent par un utilisateur non root ; `etl` et `ml` ne copient que le code exécuté, en lecture seule pour l'utilisateur de l'application (#191) ; `HEALTHCHECK` sur `api`, `etl` et le frontend ; `pip` retiré des images Python, `npm`, `corepack` et `yarn` de l'image `frontend` de production ; Trivy ne signale plus que les deux alertes de `db`. Ports : l'ETL du staging ne publie plus le 8001, PostgreSQL de développement lié à `127.0.0.1`.
- **Hooks `pre-commit`** : messages de commit, nom de branche, `ruff`, clés privées, commit direct sur `main`. Dépendances de test figées (`requirements-dev`).
- **Staging** : `:main` n'avance que si le commit est la tête de `main` (`sha-<commit>` est toujours publiée) ; `update-staging.sh` ramène le compose au commit figé.
- **Données du sujet** : DVC avec remotes `preprod` et `prod` (vérifiés le 24/10). **`httpx2`** : licence BSD-3-Clause sur PyPI (vérifiée le 26/10).
- **Politique du dépôt** : `SECURITY.md`, licence MIT, `.dockerignore` complétés, `.gitkeep` et doublons de `.env.example` retirés.

## Assumé ou écarté

- **Port 8000 du staging publié** : la recette lit le sha sur `:8000/health`, la VM n'est joignable que depuis le réseau de l'école.
- **MLflow du staging sans authentification** : lié à `127.0.0.1` de la VM, accès par tunnel SSH.
- **Collecteur absent de la production** : il interroge le mock public chaque minute ; à activer dans le `COMPOSE_PROFILES` de `production.env` sur décision d'équipe.
- **`docker-compose.staging.yml` gardé tel quel** : `deploy-production.yml` le nomme en dur, un retour vers un ancien tag échouerait après un renommage.
- **Production : auto-approbation** : les relecteurs de l'environnement `production` (six personnes) peuvent approuver leur propre déploiement (`prevent_self_review` désactivé). Choix d'équipe.
- **Bucket S3 sans versionnement et avec `force_destroy`** : le projet dure deux semaines, tout est coupé ensuite. En SSE-S3 et non KMS : coût et gestion de clé injustifiés.
- **Sortie 80/443 vers `0.0.0.0/0`** : les adresses de GHCR et de SSM ne sont pas énumérables.
- **`vite` (haute) dans `@angular/build`** : 6 alertes Dependabot ouvertes sur le fichier de verrouillage, 2 selon `npm audit` (une basse, une haute), outil de développement seulement. Le correctif demande une montée de version majeure d'Angular.
- **Image `db` : 2 alertes hautes (Trivy)**, dans le binaire de dbmate (CVE-2026-111943, CVE-2026-63209), dernière version disponible : pas de correctif possible chez nous. L'outil ne tourne qu'une fois au déploiement, sans port ouvert. À reprendre à la prochaine version de dbmate ; entrée de `.trivyignore` avec motif et échéance quand Trivy deviendra bloquant.
- **Pas de `HEALTHCHECK` sur `ml` ni `db`** : des tâches ponctuelles, pas des services.
