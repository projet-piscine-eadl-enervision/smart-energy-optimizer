# ETL

Lit l'API Mock, nettoie l'historique 2023-2024 et, plus tard, alimentera TimescaleDB. Seule la route `/health` répond (sonde Docker et supervision).

## Installation

```bash
cd etl
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\Activate
pip install -r requirements-dev.txt
```

Variables dans un `.env` (dans `etl/` ou à la racine) : `MOCK_API_URL`, `MOCK_API_USERNAME`, `MOCK_API_PASSWORD`, et `DATABASE_URL` pour les traitements qui écrivent en base (`postgresql://postgres:dev@localhost:5432/enervision` avec la base du compose local ; dans les conteneurs, le compose la fournit).

- Réseau de l'école : `MOCK_API_URL=http://10.43.43.80:8000`, identifiants vides. C'est la valeur par défaut.
- Internet : `https://api-mock.charlieandre.fr` avec l'authentification basique (notes Teams). Un 401 signifie que l'identifiant ou le mot de passe est refusé.

## Tester en local

Depuis `etl/`, environnement virtuel activé.

```bash
python -m pytest && ruff check .          # tests et lint, sans réseau, moins d'une seconde ; les tests de base sont ignorés sans DATABASE_URL (fournie par la CI)
dvc pull && python -m pipeline clean-history --output /tmp/essai.parquet   # nettoyage sur le vrai fichier
docker build -t etl-local . && docker run -d --rm --name etl-local -p 8001:8000 etl-local
docker inspect --format '{{.State.Health.Status}}' etl-local               # healthy après environ 30 s
docker rm -f etl-local
```

Client du mock, depuis le réseau de l'école :

```bash
python -c "import asyncio; from mock_client.services import site_service as s; print(asyncio.run(s.get_all_sites()))"
```

Pile complète : `docker compose up -d` à la racine, puis `docker ps` doit montrer `enervision-etl` en `healthy` (http://localhost:8001/health). `/docs` et `/sites` renvoient 404 : c'est voulu.

## Organisation

- `mock_client/client.py` : client HTTP unique (URL, authentification facultative, délai). `fetch_raw` garde la réponse telle que reçue (statut, paramètres, heure de réception, JSON), échecs compris, pour `raw.api_response`.
- `mock_client/services/` : une fonction par endpoint du mock. Elles lèvent `httpx2.HTTPStatusError` ou `httpx2.RequestError`, à l'appelant de décider. Les horodatages envoyés doivent porter un fuseau (convertis en UTC).
- `mock_client/schemas/` : réponses du mock, vérifiées sur ses réponses réelles et alignées sur les tables de la base. Horodatages en UTC (sans fuseau = UTC), `null_reasons` vide plutôt que nul, `data_quality` obligatoire.
- `pipeline/cleaning.py` : règles de remplissage des manquants, fonctions pures testées sans fichier.
- `pipeline/metadata.py` : anomalies étiquetées et contrôle des totaux, de la période et de la fréquence.
- `pipeline/timestamps.py` : horodatages ramenés en UTC.
- `pipeline/db.py`, `pipeline/runs.py`, `pipeline/raw.py` : connexion à la base (`DATABASE_URL`, autocommit), suivi de chaque traitement dans `etl.run`, réponses brutes dans `raw.api_response`.
- `pipeline/sensors.py`, `pipeline/heartbeat.py` : épisodes de panne de capteur (`core.sensor_status`) et signal de vivacité du collecteur.
- `pipeline/rows.py` : lignes prêtes à insérer en base (`core.energy_reading` : axe `time`, heure du mock, décimaux).
- `pipeline/jobs/` : un module par traitement, avec `main(argv)`. Lancement : `python -m pipeline <traitement>` (`clean-history`, `load-ref`, `poll-current`, `backfill`).
- `pipeline/provided_files/`, `pipeline/edited_files/` : données suivies par DVC, voir [`docs/donnees-dvc.md`](../docs/donnees-dvc.md).

## Nettoyage de l'historique

`dvc repro` (ou `python -m pipeline clean-history`, qui lit le CSV et `dataset_metadata.json`). Chaque colonne brute est conservée, avec `<colonne>_clean` et `<colonne>_source` (`measured`, `recovered_from_euros`, `interpolated`, `missing`), et les anomalies étiquetées des métadonnées sont reportées dans `anomaly_type` et `anomaly_severity`. Le traitement signale tout écart avec les totaux, la période et la fréquence annoncés.

Sur le fichier actuel, pour la consommation : 119 807 mesurées, 353 retrouvées par les euros (0,15 €/kWh), 1 046 interpolées, 1 441 vides. Les 1 798 zéros sont tous dans une coupure étiquetée : ce sont de vraies coupures, conservées. Une valeur manquante dans une coupure n'est jamais interpolée.

## Charger les sites

`python -m pipeline load-ref` copie `GET /sites` dans `ref.site` (les sites existants sont mis à jour) et garde la réponse dans `raw.api_response`, avec une ligne `etl.run`. À lancer une fois après les migrations, car `core.energy_reading` référence `ref.site` : `docker compose run --rm etl python -m pipeline load-ref` (sur le staging, avec `-f docker-compose.staging.yml`).

## Collecter les mesures courantes

`python -m pipeline poll-current` interroge le mock toutes les 60 s (`--interval` ou `POLL_INTERVAL_SECONDS`) : `/current` de chaque site, `/sensors/status` et `/alerts`. Chaque réponse est enregistrée telle quelle dans `raw.api_response`, puis transformée en `core.energy_reading` (`time` = heure de réception, `mock_time` = heure du mock), `core.sensor_status` (une ligne par panne, relue en base à chaque tour) et `core.alert` (`origin = 'api'`). Si `ref.site` est vide, le collecteur la charge d'abord. Un appel en échec n'arrête pas la boucle ; `SIGTERM` l'arrête proprement. `--once` fait un seul tour, pour un essai.

Un tour réussi écrit l'heure dans `/tmp/collector.heartbeat` ; `python -m pipeline.heartbeat` répond 0 si elle date de moins de trois intervalles (sonde du conteneur).

## Rattraper l'historique

`python -m pipeline backfill [--start 2023-01-01] [--end AAAA-MM-JJ[THH]] [--site SITE001]` charge l'historique du mock par pas d'une heure, un site à la fois, par fenêtres de 1000 heures (`limit` = nombre d'heures : le pas est exactement une heure, début inclus, fin exclue). Par défaut de 2023-01-01 à maintenant : environ 33 000 lignes par site, 234 000 au total, en une minute environ. Chaque appel est gardé dans `raw.api_response`, une ligne `etl.run` (`backfill`) est écrite par site, et les lignes déjà présentes sont conservées (le mock redessine un bruit à chaque appel, le premier passage fait foi) : relancer est sans danger. À la fin, `analytics.energy_hourly` est rafraîchi sur la période (sa politique automatique ne couvre que trois jours) et `analytics.site_baseline` est recalculée ; ces deux opérations exigent d'être propriétaire des vues, d'où la connexion avec le compte propriétaire.

```bash
docker compose run --rm etl python -m pipeline backfill --start 2026-10-01     # essai sur une période courte
docker compose run --rm etl python -m pipeline backfill                         # tout l'historique
```

## Collecteur en service

Service `collector` des deux compose, dans un profil à part pour ne pas solliciter le mock depuis chaque poste ni sans décision sur un serveur :

```bash
docker compose --profile collector up -d collector       # local
docker ps                                                 # collector : healthy après environ 90 s
docker compose logs -f collector                          # une ligne par tour
```

Sur le staging, ajouter `collector` à `COMPOSE_PROFILES` dans `/etc/enervision/staging.env` (`COMPOSE_PROFILES=apps,collector`) ; la mise à jour automatique le démarre. Le conteneur passe `unhealthy` si aucun tour n'a réussi depuis trois intervalles (mock injoignable, base arrêtée). La production ne collecte pas tant que `collector` n'est pas dans le `COMPOSE_PROFILES` de `production.env`.

## Ajouter un traitement

1. Créer `pipeline/jobs/<nom>.py` avec `main(argv)` ; garder les règles dans un module sans fichier ni réseau pour les tester.
2. L'inscrire dans `JOBS` de `pipeline/__main__.py`.
3. Planification : un traitement qui boucle (collecte toutes les 10 à 60 s, ce que cron ne sait pas faire) devient un service compose sur la même image, avec `command: python -m pipeline <traitement>`. Un traitement ponctuel se lance avec `docker compose run --rm etl python -m pipeline <traitement>`, ou par un minuteur systemd sur la VM.
