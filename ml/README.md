# Module ML

Prévoit la consommation de chaque site pour les **24 prochaines heures**, heure par heure, et signale les **pics**. Les prédictions sont écrites dans `ml.prediction`, que l'API lit.

```
TimescaleDB (analytics.energy_hourly, ref.site)
        │  historique horaire
        ▼
  entraînement ──► MLflow (registre : challenger → champion)
                          │  champion
                          ▼
                     prédiction ──► TimescaleDB (ml.prediction) ──► API ──► front
```

Le module ne parle qu'à la base et à MLflow, jamais à l'API Mock ni au backend.

## Lancer

Depuis la racine du projet, base et MLflow démarrés (`docker compose up -d`) :

```bash
# Entraîner : challenger, promu champion s'il bat l'actuel
docker compose run --rm ml                                            # profil (par défaut)
docker compose run --rm ml python train.py --model seasonal_naive     # modèle de comparaison

# Prévoir les 24 prochaines heures avec le champion
docker compose run --rm ml python -m enervision_ml.predict
```

Résultats dans le MLflow de développement : http://localhost:5000 (expérience `enervision`, modèle `enervision-consumption`).

La prévision se relance à la main ou, sur le staging, toutes les heures à `hh:05` par un minuteur systemd (`predict-ml.timer`, voir `docs/deploiement-staging.md`). Après avoir écrit les prévisions, elle recalcule les recommandations (`app.refresh_recommendations()`) ; si ce calcul échoue, les prévisions restent écrites mais la commande se termine en erreur. Elle refuse d'écrire si la dernière mesure a plus de 3 heures (collecteur arrêté) : les prévisions porteraient sur des heures passées.

### Données attendues de l'ETL

Le ML lit `analytics.energy_hourly`. L'historique du rattrapage horaire (`python -m pipeline backfill`) n'y apparaît qu'après le rafraîchissement de l'agrégat, que le rattrapage lance : sans lui, l'entraînement s'arrête (moins de 365 jours). Le collecteur complète ensuite heure par heure.

La fin du jeu est figée pour que deux entraînements donnent les mêmes chiffres : `ML_DATA_END` (date ISO, UTC) si elle est définie, sinon minuit UTC du jour. Les fenêtres de validation et de test ne glissent donc qu'une fois par jour. La valeur utilisée est enregistrée dans MLflow (`data_end`) et dans `ml.model_run.data_end`.

```bash
ML_DATA_END=2026-10-25 docker compose run --rm ml
```

### Sur le staging

Compose : `docker-compose.staging.yml`. Le suivi des modèles (`mlflow`) s'ajoute à `COMPOSE_PROFILES` ; l'entraînement et la prévision se lancent à la demande, jamais en service (une mise à jour toutes les 2 minutes les relancerait).

```bash
# staging.env : COMPOSE_PROFILES=apps,collector,mlflow
C="docker compose -f docker-compose.staging.yml --env-file /etc/enervision/staging.env"
$C pull ml && $C up -d
$C run --rm ml                                      # entraîne un challenger
$C run --rm ml python -m enervision_ml.predict      # prévoit les 24 prochaines heures
```

MLflow n'a pas d'authentification : sur la VM, il écoute sur `127.0.0.1:5000` et n'est atteignable que par un tunnel SSH. L'adresse à ouvrir depuis le poste dépend de l'environnement :

| Où tourne l'entraînement | Adresse à ouvrir depuis le poste |
|---|---|
| Développement (`docker compose` local) | `http://localhost:5000` |
| Staging (VM, avec le tunnel) | `http://localhost:5001` |
| Production | aucune, MLflow n'y est pas déployé |

Pour ouvrir celui du staging, lancer **depuis le poste** (pas depuis la VM) `ssh -L 5001:127.0.0.1:5000 root@<VM>`, laisser la fenêtre ouverte, puis aller sur http://localhost:5001. Le port 5000 est celui du MLflow de développement : si le compose local tourne, c'est lui qui répond, et on voit une autre base, sans l'expérience `enervision` du staging.

L'entraînement affiche en dernière ligne `lien MLflow : …`, déjà construit pour l'environnement avec la variable `MLFLOW_PUBLIC_URL` des fichiers compose (sans elle, l'adresse de suivi du module), et rien en production (`APP_ENV=production`). Les deux lignes `View run` de MLflow qui le précèdent montrent l'adresse du réseau Docker (`http://mlflow:5000/…`) : elle ne s'ouvre pas depuis le poste.

Le module utilise le compte propriétaire de la base, comme l'ETL, en attendant les comptes par module (ticket #145). Sans historique chargé, `run --rm ml` s'arrête sur « Historique insuffisant » et `predict` sur « Aucun modèle champion » : les connexions à la base et à MLflow fonctionnent.

### Données en local (développement)

Tant que l'ETL ne charge pas l'historique, `scripts/seed_dev.py` charge le CSV du sujet dans `core.energy_reading` et rafraîchit `analytics.energy_hourly`. Les schémas de l'équipe (`ref`, `core`, `analytics`, `ml`) doivent déjà exister.

```bash
cp "<dossier du sujet>/data/all_sites_combined.csv" ml/data/   # ignoré par Git
docker compose run --rm ml python scripts/seed_dev.py
```

Le script refuse de tourner si `APP_ENV` n'est pas `dev` (le service `ml` du staging fixe `APP_ENV=staging`). Le CSV n'est pas le mock (niveaux, noms des sites, anomalies) : il sert à faire tourner le code, pas à évaluer le modèle, qui s'entraîne sur l'historique du mock chargé par l'ETL. Ce jeu d'entraînement doit être **figé et commun** à l'équipe : le mock redessine son bruit à chaque appel, deux chargements ne donnent pas les mêmes données.

## Stratégie

Elle s'appuie sur l'[analyse de l'API Mock](../docs/analyse-api-mock.md) (constats cités par numéro).

**Ce que sont les données.** Un profil fixe (site, mois, type de jour, heure) multiplié par un bruit gaussien de 5 % sans mémoire d'un point au suivant (constats 3 à 5). Tout ce qui est prévisible est dans le profil ; le reste est du hasard. Sur une moyenne horaire, l'erreur ne peut pas descendre sous environ 4 % en nMAE.

**Problème.** Une régression : prévoir la consommation horaire, puis en déduire les **pics de demande**.

| | Pic de demande (ce module) | Pic anormal (ETL, alertes `rule`) |
|---|---|---|
| Définition | prévision > 1,25 × consommation moyenne du site | mesure > profil + 15 % (3 écarts-types) |
| Prévisible | oui, c'est le profil | non (`/simulate/spike`) |
| Usage | recommandations : décaler les usages avant le pic | alertes en temps réel |

Un seuil en quantile ou en part de la capacité ne convient pas : il marquerait du bruit comme pic sur les sites plats, datacenter et hôpital (constat 9).

**Variables** (`features.py`). Uniquement ce qui est connu au moment de prévoir :

| Variable | Pourquoi |
|---|---|
| `hour_of_day`, `day_of_week`, `is_weekend`, `month` | le profil ; en **UTC**, que suit le mock sans changement d'heure (constat 11) |
| `lag_24`, `lag_168` | même heure la veille, la semaine dernière ; utilisés seulement par le modèle de comparaison |

Écartées : la température, qui n'explique pas la consommation (constat 7) ; `current_a`, copie de la cible (constat 13) ; l'ensoleillement et le coût, absents du mock (constat 14) ; les jours fériés, ignorés par le mock (constat 6). Une heure dont plus de la moitié des mesures n'ont pas de consommation est traitée comme absente (`nb_missing`, constat 10). Aucune variable tirée des mesures n'a un décalage inférieur à 24 h : un test le vérifie (`test_no_future_leakage`).

**Modèles** (`models.py`).
1. `site_profile` : moyenne de l'entraînement par site, mois, type de jour et heure. C'est la meilleure prévision possible sur ces données, et la référence que tout modèle doit battre.
2. `seasonal_naive` : même heure la semaine dernière. Il recopie le bruit de la semaine passée et fait environ 1,4 fois moins bien que le profil (vérifié par `test_profile_beats_naive_on_mock_like_data`) : la preuve que les mesures récentes n'apportent rien.
3. Un modèle plus complexe (LightGBM) peut être proposé comme challenger ; il n'est pas attendu qu'il batte le profil, puisque le reste est du bruit.

**Évaluation** (`evaluate.py`). Découpage dans l'ordre du temps, jamais aléatoire : entraînement, puis validation (60 derniers jours avant le test), puis test (60 derniers jours). L'entraînement doit couvrir **au moins un an**, sinon le facteur du mois n'est pas appris (constat 5) : l'entraînement s'arrête avec un message clair. Le profil est calculé sur l'entraînement seulement : `analytics.site_baseline`, calculée par l'ETL sur toutes les données, ne doit pas servir de modèle (fuite de la validation et du test).

| Métrique | Rôle |
|---|---|
| `nmae` | erreur relative moyenne des sites ; **départage challenger et champion** |
| `mae`, `mae_SITE00X` | erreur en kW, globale et par site |
| `peak_precision`, `peak_recall`, `peak_f1` | qualité de la détection des pics |
| `coverage` | part des heures que le modèle a pu prévoir |

La nMAE est utilisée plutôt que la MAE pour qu'une usine à 600 kW ne pèse pas plus qu'un bureau à 100 kW. Le test donne le chiffre final et ne sert à aucune décision.

**Impact métier** (`evaluate.business_kpis`). Processus simulé : la veille, le gestionnaire reçoit les pics prévus et décale 10 % de la consommation de ces heures vers les heures creuses ; chaque kWh au-dessus du seuil de pic est facturé 0,15 €. Ces deux valeurs sont des **hypothèses** (`SHIFTABLE_RATIO`, `PEAK_PENALTY_EUR_KWH` dans `config.py`), le mock ne donnant aucun coût (constat 14). Sans modèle, aucun pic n'est annoncé et rien n'est évité.

| KPI | Rôle |
|---|---|
| `kpi_peak_kwh_avoided` | dépassement évité grâce aux pics annoncés (kWh) |
| `kpi_peak_avoided_ratio` | part du dépassement qu'une prévision parfaite aurait évité |
| `kpi_penalty_saved_eur` | dépassement évité valorisé en euros |
| `kpi_missed_peak_hours`, `kpi_false_alarm_hours` | pics non annoncés, alertes inutiles |
| `test_nmae_gain_vs_naive`, `test_kpi_penalty_gain_vs_naive_eur` | ce que le modèle apporte en plus du naïf, sur le même test |

Sur des données construites comme le mock (test `test_impact_and_data_recorded_in_mlflow`), le profil réduit l'erreur d'environ 30 % par rapport au naïf, mais les deux annoncent tous les pics : les pics de bureau dépassent le seuil de loin. Le gain en euros sur le naïf est alors nul ; il viendra des sites où le pic est proche du seuil, à vérifier sur les données du mock.

**Versions** (MLflow). Chaque entraînement crée une version du modèle `enervision-consumption`, rattachée à son run : paramètres, métriques, version du code (`code_version`, le commit) et empreinte des données de chaque période (onglet *Datasets* du run, contextes `training`, `validation`, `test`). Deux runs sur les mêmes données ont la même empreinte. Les alias `champion` et `challenger` désignent les versions en service.

**Promotion** (`training.py`, règle de `CONTRIBUTING.md`). Chaque entraînement enregistre une version `challenger`. Le champion est réévalué **sur la validation actuelle** (les données s'enrichissent avec le temps), et le challenger le remplace seulement si sa nMAE est plus basse. La décision est notée dans le tag `decision` du run.

## Suivi en SQL (Grafana)

Chaque entraînement copie en base ce que MLflow garde pour lui, et des vues comparent les prédictions à la mesure réelle (migration `db/migrations/20261026120000_ml_monitoring.sql`). Une source PostgreSQL suffit à Grafana, sans MLflow ni Prometheus.

| Objet | Contenu | Usage dans Grafana |
|---|---|---|
| `ml.model_run` | une ligne par version : modèle, période d'entraînement, promue à son entraînement (`promoted`), champion actuel (`is_champion`, une seule ligne), décision, hypothèses du KPI | historique des versions, champion actuel (`WHERE is_champion`) |
| `ml.model_metric` | métriques de l'entraînement (`val_nmae`, `test_nmae`, `test_kpi_penalty_saved_eur`, `test_nmae_gain_vs_naive`…) | notes de chaque version, gain sur le naïf |
| `ml.peak_threshold` | seuil de pic par version et par site | référence des vues |
| `ml.prediction_vs_actual` | chaque prévision passée face à la mesure : erreur, pic annoncé, pic réel, kWh évités | courbe prévu / réel |
| `ml.prediction_quality_daily` | par jour, site et version : nMAE réelle, pics annoncés / ratés / fausses alertes, kWh et € évités | **dérive de la performance** (C33), **impact métier en production** (C35) |
| `ml.prediction_freshness` | dernière prédiction par site et son âge | alerte si l'âge dépasse 2 h |

Mêmes règles qu'à l'entraînement : heure à plus de 50 % de mesures nulles écartée, dépassement évité calculé comme `evaluate.business_kpis`. Les vues ne se remplissent qu'une fois les prédictions passées confrontées aux mesures, donc avec la prédiction horaire en service. Le rôle de lecture de Grafana a besoin de `SELECT` sur ces objets (`USAGE` sur le schéma `ml`).

Exemple, nMAE réelle par jour et par version :

```sql
SELECT day AS time, model_version, avg(nmae) AS nmae
FROM ml.prediction_quality_daily
WHERE $__timeFilter(day)
GROUP BY day, model_version
ORDER BY day;
```

## Structure

```
ml/
├── train.py                 # point d'entrée de l'image : entraînement
├── enervision_ml/
│   ├── config.py            # constantes (horizon, fuseau, seuil des pics, découpage) et variables d'environnement
│   ├── data.py              # seul module qui connaît le schéma : lit analytics/ref, écrit ml.prediction
│   ├── features.py          # variables d'entrée
│   ├── models.py            # modèles et enveloppe MLflow (prévision + pics)
│   ├── evaluate.py          # découpage temporel et métriques
│   ├── registry.py          # alias champion / challenger
│   ├── training.py          # entraînement et promotion
│   └── predict.py           # prédiction des 24 prochaines heures
├── scripts/seed_dev.py      # développement uniquement : CSV du sujet → base locale
├── data/                    # CSV du sujet, ignoré par Git
└── tests/                   # MLflow en SQLite temporaire ; base seulement pour test_data_db.py
```

## Tests

Depuis `ml/`, comme la CI :

```bash
ruff check .
pytest --cov=enervision_ml
```

`test_pipeline.py` enchaîne entraînement, promotion et prédiction avec un MLflow en fichier SQLite temporaire et des données factices : ni base ni serveur nécessaires. `test_data_db.py` teste les requêtes SQL de `data.py` avec le rôle `enervision_ml` ; il est ignoré sans `DATABASE_URL`, que la CI fournit (base migrée par `db/migrations`, par exemple `DATABASE_URL=postgresql://postgres:…@localhost:5432/postgres`).
