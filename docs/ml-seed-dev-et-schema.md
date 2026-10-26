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

## Problème 2 : le CSV et le mock partagent les mêmes `site_id` (réglé : table séparée)

Le CSV et le mock utilisent `SITE001` à `SITE007`, mais pas les mêmes données (`docs/analyse-api-mock.md`, constat 14) : noms par type ou par ville, anomalies étiquetées que le mock n'a pas, niveaux différents. Sur la même semaine (4 au 10 mars 2024), le CSV est de 0 % à 30 % au-dessus du mock selon le site (SITE002 : 1,0 ; SITE001 et SITE003 : 1,2 ; SITE005 et SITE006 : 1,3).

Chargé dans `core.energy_reading` à côté du rattrapage du mock, le CSV prendrait les mêmes clés `(site_id, time)` : une des deux sources serait écartée sans erreur, et `analytics.site_baseline` comme l'entraînement mélangeraient deux niveaux.

**Décision d'équipe (25/10) : le parquet nettoyé est chargé en base, dans une table séparée `ml.history_labeled`**, pour la détection d'anomalies (seules données étiquetées) : consommation nettoyée, source du nettoyage, température, humidité, rayonnement, type et gravité de l'anomalie. Rien dans `core` ni `analytics` : la base de l'environnement partagé pour les mesures reste celle du mock (collecteur `/current`, rattrapage `/readings` à pas d'une heure depuis 2023-01-01).

- Le détecteur doit raisonner en écart au profil du site (mois, type de jour, heure, calculé sur ce CSV) ou en taux de charge (`kW / capacity_kw`), jamais sur les kW bruts, puis s'appliquer au flux du mock avec `analytics.site_baseline`.
- Chargement (lot ETL à venir) : `python -m pipeline load-history <fichier.parquet>`, rejouable. Les noms de sites restent ceux de `ref.site`, chargés depuis le mock.
- Les valeurs `anomaly_type` (`plateau`, `outage`, `drop`, `spike`) et `anomaly_severity` (`medium`, `high`, `critical`) existent dans `ref.alert_type` et `ref.severity` : clés étrangères sans conversion.

`seed_dev.py` reste un outil de développement **local** : le script refuse déjà de tourner hors `APP_ENV=dev`, et il ne doit jamais servir sur une base où le rattrapage du mock a tourné. Le README du module ML le dit : le CSV sert « à faire tourner le code, pas à évaluer le modèle ».

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
