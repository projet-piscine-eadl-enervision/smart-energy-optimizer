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

Résultats dans MLflow : http://localhost:5000 (expérience `enervision`, modèle `enervision-consumption`).

La prédiction toutes les heures viendra avec le service ML (planificateur intégré et `POST /predictions/run`).

### Données en local (développement)

Tant que l'ETL ne charge pas l'historique, `scripts/seed_dev.py` charge le CSV du sujet dans `core.energy_reading` et rafraîchit `analytics.energy_hourly`. Les schémas de l'équipe (`ref`, `core`, `analytics`, `ml`) doivent déjà exister.

```bash
cp "<dossier du sujet>/data/all_sites_combined.csv" ml/data/   # ignoré par Git
docker compose run --rm ml python scripts/seed_dev.py
```

Le script refuse de tourner si `APP_ENV` n'est pas `dev`. Le CSV n'est pas le mock (niveaux, noms des sites, anomalies) : il sert à faire tourner le code, pas à évaluer le modèle, qui s'entraîne sur l'historique du mock chargé par l'ETL. Ce jeu d'entraînement doit être **figé et commun** à l'équipe : le mock redessine son bruit à chaque appel, deux chargements ne donnent pas les mêmes données.

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

Écartées : la température, qui n'explique pas la consommation (constat 7) ; `current_a`, copie de la cible (constat 13) ; l'ensoleillement et le coût, absents du mock (constat 14) ; les jours fériés, ignorés par le mock (constat 6). Une heure dont plus de la moitié des mesures n'ont pas de consommation est traitée comme absente (`nb_missing`, constat 10). Aucune variable tirée des mesures n'a un décalage inférieur à 24 h : un test le vérifie (`test_aucune_fuite_du_futur`).

**Modèles** (`models.py`).
1. `site_profile` : moyenne de l'entraînement par site, mois, type de jour et heure. C'est la meilleure prévision possible sur ces données, et la référence que tout modèle doit battre.
2. `seasonal_naive` : même heure la semaine dernière. Il recopie le bruit de la semaine passée et fait environ 1,4 fois moins bien que le profil (vérifié par `test_profil_bat_le_naif_sur_des_donnees_comme_le_mock`) : la preuve que les mesures récentes n'apportent rien.
3. Un modèle plus complexe (LightGBM) peut être proposé comme challenger ; il n'est pas attendu qu'il batte le profil, puisque le reste est du bruit.

**Évaluation** (`evaluate.py`). Découpage dans l'ordre du temps, jamais aléatoire : entraînement, puis validation (60 derniers jours avant le test), puis test (60 derniers jours). L'entraînement doit couvrir **au moins un an**, sinon le facteur du mois n'est pas appris (constat 5) : l'entraînement s'arrête avec un message clair. Le profil est calculé sur l'entraînement seulement : `analytics.site_baseline`, calculée par l'ETL sur toutes les données, ne doit pas servir de modèle (fuite de la validation et du test).

| Métrique | Rôle |
|---|---|
| `nmae` | erreur relative moyenne des sites ; **départage challenger et champion** |
| `mae`, `mae_SITE00X` | erreur en kW, globale et par site |
| `peak_precision`, `peak_recall`, `peak_f1` | qualité de la détection des pics |
| `coverage` | part des heures que le modèle a pu prévoir |

La nMAE est utilisée plutôt que la MAE pour qu'une usine à 600 kW ne pèse pas plus qu'un bureau à 100 kW. Le test donne le chiffre final et ne sert à aucune décision.

**Promotion** (`training.py`, règle de `CONTRIBUTING.md`). Chaque entraînement enregistre une version `challenger`. Le champion est réévalué **sur la validation actuelle** (les données s'enrichissent avec le temps), et le challenger le remplace seulement si sa nMAE est plus basse. La décision est notée dans le tag `decision` du run.

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
└── tests/                   # sans base ni serveur (MLflow en SQLite temporaire)
```

## Tests

Depuis `ml/`, comme la CI :

```bash
ruff check .
pytest --cov=enervision_ml
```

`test_pipeline.py` enchaîne entraînement, promotion et prédiction avec un MLflow en fichier SQLite temporaire et des données factices : ni base ni serveur nécessaires. Seules les requêtes SQL de `data.py` ne sont pas couvertes, elles demandent TimescaleDB et les schémas de l'équipe.
