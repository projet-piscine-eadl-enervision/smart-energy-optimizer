# `seed_dev.py` (branche `ml-structure`) face au schéma de la base

Pour Naycen (module ML). Vérifié le 24/10/2026 sur `main` à `89c7ab7` (migrations de la PR #134) et `ml-structure` à `6dd53f6`, et revu le 25/10 : `ml-structure` n'a pas bougé, le problème 1 reste à corriger. Aucune branche n'a été modifiée : tout est reproductible ci-dessous.

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

## Problème 2 : le CSV et le mock partagent les mêmes `site_id` (réglé par la décision d'équipe)

Le CSV et le mock utilisent `SITE001` à `SITE007`, mais pas les mêmes données (`docs/analyse-api-mock.md`, constat 14) : noms par type ou par ville, niveaux plus élevés dans le CSV (SITE001 : 112,7 kW contre 94), anomalies étiquetées que le mock n'a pas.

Chargé dans `core.energy_reading` à côté du rattrapage du mock, le CSV prendrait les mêmes clés `(site_id, time)` : `ON CONFLICT DO NOTHING` garderait l'une des deux sources selon l'ordre de chargement, et `analytics.site_baseline` comme l'entraînement mélangeraient deux niveaux. **Décision d'équipe : le parquet nettoyé n'est pas chargé en base.** La base de l'environnement partagé ne vient que du mock : collecteur `/current` et rattrapage `/readings` à pas d'une heure depuis 2023-01-01. Le parquet (suivi par DVC, voir `docs/donnees-dvc.md`) sert à l'exploration et à la détection d'anomalies (seules données étiquetées) par `dvc pull`.

Donc `seed_dev.py` reste un outil de développement **local** : le script refuse déjà de tourner hors `APP_ENV=dev`, et il ne doit jamais servir sur une base où le rattrapage du mock a tourné. Le README du module ML le dit : le CSV sert « à faire tourner le code, pas à évaluer le modèle ».

À rouvrir si le ML d'anomalies ou le dashboard exigent ces données en base : migration pour une valeur `source = 'history'`, règle pour `data_quality` (mesuré = `good`, retrouvé ou interpolé = `partial`, vide = `critical`) écrite dans `pipeline/rows.py`, et accord sur `ref.site`. Le nettoyage n'a pas à changer.

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
