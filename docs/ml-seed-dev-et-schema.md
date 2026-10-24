# `seed_dev.py` (branche `ml-structure`) face au schéma de la base

Pour Naycen (module ML) et Carole (base de données). Vérifié le 24/10/2026 sur `main` à `89c7ab7` (migrations de la PR #134) et `ml-structure` à `6dd53f6`. Aucune de ces deux branches n'a été modifiée : tout est reproductible ci-dessous.

## Ce qui a été vérifié

Le module ML lit `analytics.energy_hourly` et `ref.site`, et écrit `ml.prediction`. Ces trois objets existent dans les migrations et leurs colonnes correspondent à `ml/enervision_ml/data.py`. Seul `ml/scripts/seed_dev.py`, qui remplit `core.energy_reading` depuis le CSV du sujet, pose problème.

## Problème 1 : le script échoue (à corriger dans `ml-structure`)

`core.energy_reading.mock_time` est `NOT NULL` sans valeur par défaut. Le `COPY` de `seed_dev.py` ne le remplit pas :

```
psycopg.errors.NotNullViolation: null value in column "mock_time" of relation "seed"
violates not-null constraint
```

Correctif, deux lignes dans le `COPY` (le CSV n'a qu'une heure, celle de la grille, qui sert aux deux colonnes comme pour tous les rattrapages) :

```diff
-                "COPY seed (time, site_id, consumption_kw, temperature_celsius, "
+                "COPY seed (time, mock_time, site_id, consumption_kw, temperature_celsius, "
@@
                             r.time,
+                            r.time,
                             r.site_id,
```

Avec ce seul correctif : 7 sites, 122 647 mesures de 2023-01-01 à 2024-12-31, `analytics.energy_hourly` rafraîchi (122 647 heures), et la requête `HOURLY_QUERY` du ML renvoie les 122 647 lignes.

## Problème 2 : le CSV et le mock partagent les mêmes `site_id` (à décider)

Le CSV et le mock utilisent `SITE001` à `SITE007`, mais pas les mêmes données (`docs/analyse-api-mock.md`, constat 14) :

- noms par type de site dans le CSV (« Bureau Tertiaire »), par ville dans le mock ;
- niveaux plus élevés dans le CSV (SITE001 : 112,7 kW contre 94) ;
- le CSV n'a pas `voltage_v`, `current_a`, `power_factor`, mais a des anomalies étiquetées que le mock n'a pas.

Conséquences si le CSV est chargé dans `core.energy_reading` à côté des données du mock :

- la clé `(site_id, time)` est la même : si le rattrapage du mock couvre 2023-2024, `ON CONFLICT DO NOTHING` garde silencieusement les valeurs du CSV, ou l'inverse selon l'ordre de chargement (à vérifier sur la plage réellement servie par `/readings`) ;
- `ref.site` est rempli par `ON CONFLICT (site_id) DO NOTHING` avec des noms du CSV et une `capacity_kw` approximée par le maximum observé : l'ETL, qui charge ensuite les vrais sites depuis `GET /api/v1/sites`, les trouverait déjà là ;
- `analytics.site_baseline` et l'entraînement du ML mélangeraient deux sources de niveaux différents.

Le README du module ML dit déjà que le CSV sert « à faire tourner le code, pas à évaluer le modèle ». Le script ne le garantit pas : il écrit dans les mêmes tables que la production.

À trancher avec Carole : une valeur de `source` distincte pour le CSV (nouvelle migration, la contrainte actuelle n'autorise que `current` et `readings`), ou une table séparée, ou un usage limité à une base locale jetable (le script refuse déjà de tourner hors `APP_ENV=dev`).

## Chargement de l'historique nettoyé (décision d'équipe)

Le parquet nettoyé (suivi par DVC, voir `docs/donnees-dvc.md`) n'est **pas chargé en base** pour l'instant. Les données de la base viennent du mock : collecteur `/current` et rattrapage `/readings` à pas d'une heure depuis 2023-01-01, ce qui évite le mélange du problème 2. Le parquet sert à l'exploration et à la détection d'anomalies (seules données étiquetées) par `dvc pull`.

À rouvrir si le ML d'anomalies ou le dashboard exigent ces données en base : migration pour une valeur `source = 'history'`, règle pour `data_quality` (mesuré = `good`, retrouvé ou interpolé = `partial`, vide = `critical`) écrite dans `pipeline/rows.py`, et accord de Carole sur `ref.site`. Le nettoyage n'a pas à changer. `seed_dev.py` reste un outil de développement local.

## Reproduire

Depuis la racine du dépôt, sur `main` :

```bash
docker compose up -d db
docker compose run --rm migrate                      # applique db/migrations
git show origin/ml-structure:ml/scripts/seed_dev.py > /tmp/seed_dev.py
# le CSV du sujet est dans etl/pipeline/provided_files/ après `dvc pull`
DATABASE_URL=postgresql://postgres:dev@localhost:5432/enervision APP_ENV=dev \
  python /tmp/seed_dev.py etl/pipeline/provided_files/all_sites_combined.csv
```

Sans le correctif : l'erreur `mock_time` ci-dessus. Avec : la ligne `7 sites, 122647 mesures insérées`.

Dépendances du script : `pandas`, `psycopg[binary]`, `python-dotenv`.
