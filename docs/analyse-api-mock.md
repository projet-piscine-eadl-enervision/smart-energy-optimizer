# Analyse de l'API Mock

Mesures faites les 22 et 23/10/2026 sur l'API Mock de l'école (URL interne, sans authentification). Chaque constat est suivi de sa preuve et de ses conséquences pour l'ETL et pour le ML. Ce qui n'est pas confirmé est regroupé à la fin.

Documents liés : [environnements techniques](environnements-techniques.md).

## À retenir

1. Les données sont **générées à la demande** : redemander la même fenêtre donne d'autres valeurs. Notre base est la seule source de vérité.
2. La consommation est une **fonction déterministe** du type de site, de l'heure, du type de jour et du mois, plus un **bruit gaussien de 5 %**. Il n'y a ni jours fériés ni anomalie spontanée.
3. Temps réel : `/current`. Historique : `/readings`, une seule fois.
4. Les nulls sont des **pannes de capteur de 45 secondes au plus**, annoncées par `/sensors/status` avec une heure de fin. `/current` renvoie une consommation nulle dans environ **26 %** des relevés (mesuré sur une heure). Le dashboard doit afficher la dernière valeur connue et son âge.
5. Le fuseau du mock a changé en 24 heures : l'axe du temps est l'heure de réception en UTC, relevée par notre code.
6. `consumption_kwh` est une copie de `consumption_kw`, et le courant `current_a` en est quasi une autre : ni l'un ni l'autre ne sont des variables explicatives. La température du mock n'explique pas la consommation.
7. Pour le ML, le **profil attendu** (type de site, heure, type de jour, mois) est la référence à battre : l'erreur ne peut pas descendre sous 5 % par point.

## Méthode

Scripts Python (non versionnés) lancés depuis WSL : appels ponctuels, une semaine complète (lundi 4 au dimanche 10 mars 2024, 7 sites, 49 000 mesures), les 52 mercredis de 2024 (10 h à 17 h, 100 points par site), un mercredi de mi-mois pour chaque mois de 2024 (200 points par site), le même jour de mars en 2020, 2023 et 2025, deux journées complètes au pas de 5 minutes (mercredi 13 et dimanche 10 mars 2024), six appels répétés sur une même journée, cinq minutes de collecte sur `/current` à 10 secondes pour 7 sites, et trois minutes de relevés croisés de `/sensors/status` et `/current`. Les notebooks de l'équipe ML sont comparés dans l'avant-dernière section.

## Constats

### 1. Données générées à la demande

**Constat.** Rien n'est stocké côté mock. Chaque appel redessine un bruit autour du profil.
**Preuve.** Trois appels sur la même heure de l'usine SITE002 : 899,6, 894,8 et 900,2 kW, avec les mêmes horodatages. L'historique est accessible aussi loin qu'on le demande (2020 testé) ; le futur, ou un `start_time` postérieur à `end_time`, renvoie 400 ; `limit` au-dessus de 1000 renvoie 422 ; un site inconnu, 404.
**ETL.** Le rattrapage est unique et non reproductible : conserver les réponses brutes (`raw`) et faire partir toute l'équipe de la même base ou du même fichier d'initialisation.
**ML.** Figer un jeu d'entraînement dans un fichier : deux membres qui rejouent le rattrapage n'ont pas les mêmes données.

### 2. Deux endpoints, deux usages

**Constat.** `/readings` renvoie une grille régulière de `limit` points sur la fenêtre (pas = fenêtre divisée par `limit`), sans pas natif. `/current` renvoie une valeur nouvelle à chaque appel, horodatée par le serveur.
**Preuve.** Pas de 0,6 s pour 10 minutes avec `limit=1000`, de 3600 s pour 24 h avec `limit=24`. Sans `site_id`, `limit` est réparti à parts égales (142 points par site pour 1000). `/current` répond en moins de 10 ms. Le dernier point de `/readings` ne coïncide pas avec l'instant présent.
**ETL.** Collecteur sur `/current` pour les 7 sites toutes les 10 à 60 secondes (à 10 s : environ 60 000 lignes par jour). Rattrapage par `/readings`, un site à la fois, sur une grille fixe, avec insertion `ON CONFLICT` sur (`time`, `site_id`).

### 3. Profil déterministe et bruit de 5 %

**Constat.** Chaque point vaut le profil du site multiplié par un bruit gaussien de 5 %, sans mémoire d'un point au suivant.
**Preuve.** Six appels sur le mercredi 13/03/2024 au pas de 5 minutes : écart relatif de 4,9 %, 5,0 % et 5,0 % (SITE001 à SITE003), autocorrélation d'un point au suivant de +0,02 à +0,07, résidu maximal de 13,9 % à 15,7 % (environ 3 écarts-types).
**ML.** L'erreur d'un modèle ne peut pas descendre sous 5 % par point ; sur la moyenne d'une heure (12 points à 5 minutes), elle tombe à environ 1,5 %. Prévoir et évaluer sur des agrégats horaires, pas sur des points isolés. Comme le signal est une table (site, heure, type de jour, mois), la moyenne par ces clés (`analytics.site_baseline`) est la **référence de comparaison** : un modèle qui ne fait pas mieux n'apporte rien.

### 4. Forme horaire et week-end

**Constat.** Les bureaux, les usines et le commerce ont une forme horaire en semaine et un niveau plat le week-end. Le datacenter et l'hôpital sont plats toute la semaine.
**Preuve.** Moyennes de la semaine d'échantillon (kW) :

| Site | Type | Capacité | Moyenne | Nuit, semaine (0 h à 6 h) | Jour, semaine (10 h à 17 h) | Jour, week-end | Maximum |
|---|---|---|---|---|---|---|---|
| SITE001 | bureau | 200 | 94 | 62 | 167 | 74 | 196 |
| SITE002 | usine | 1000 | 564 | 270 | 904 | 340 | 1061 |
| SITE003 | datacenter | 800 | 735 | 746 | 729 | 732 | 892 |
| SITE004 | commerce | 400 | 236 | 123 | 323 | 288 | 385 |
| SITE005 | hôpital | 600 | 476 | 485 | 472 | 473 | 576 |
| SITE006 | bureau | 180 | 83 | 55 | 145 | 65 | 169 |
| SITE007 | usine | 950 | 525 | 247 | 848 | 312 | 991 |

Transitions du mercredi 13/03/2024 (kW, par heure) : bureau SITE001, 62,6 à 7 h, 85,4 à 8 h, 122,5 à 9 h, 168,2 à 10 h, puis 168,7 à 17 h, 124,8 à 18 h, 62,7 à 19 h. Usine SITE002, 272,6 à 5 h, 403,9 à 6 h, 652,2 à 7 h, 900,5 à 8 h, puis 920,5 à 20 h, 655,1 à 21 h, 267,4 à 22 h. Commerce SITE004, 122,0 à 8 h, 171,9 à 9 h, 253,3 à 10 h, 339,6 à 11 h, puis 337,3 à 19 h, 254,1 à 20 h, 123,7 à 21 h. Dimanche 10/03/2024 : bureau entre 71 et 75 kW toute la journée, usine entre 329 et 351, commerce entre 275 et 296.
**Sites d'un même type.** Les niveaux sont proches de la proportionnalité à la capacité : le second bureau consomme 0,88 fois le premier (capacité 0,90), la seconde usine 0,93 fois la première (capacité 0,95).
**ML.** Variables utiles : heure, type de jour (semaine ou week-end), type de site. Le week-end n'a pas de forme horaire. Un modèle commun à tous les sites, sur le taux de charge (`kW / capacity_kw`) avec le type de site en variable, suffit à représenter les sept sites. Le datacenter, le commerce et l'hôpital n'ont qu'un site chacun : un modèle « par catégorie » y revient à un modèle par site. Une variable « site actif » (`is_scheduled_active`) se définit par les plages de ce constat (bureaux 8 h à 19 h, usines 6 h à 21 h, commerce 9 h à 20 h en semaine), sans jamais être déduite de la consommation cible.

### 5. Saisonnalité : un facteur par mois

**Constat.** Un facteur mensuel commun aux sites : deux creux (janvier, juillet) et deux sommets (avril, octobre), identique chaque année.
**Preuve.** Mercredi de mi-mois, 10 h à 17 h (kW) : SITE001, 149,8 en janvier, 170,5 en avril, 151,7 en juillet, 168,9 en octobre ; SITE002, 794,1, 916,6, 801,6 et 914,6 ; SITE003, 698,6, 732,7, 695,9 et 735,5. Mercredi de mi-mars, SITE001 : 168,0 (2020), 167,8 (2023), 168,0 (2024), 167,3 (2025). Confirmé sur les 52 mercredis de 2024 (10 h à 17 h, 100 points par site) : par rapport au sommet, bureaux, usines et commerce sont à 0,87 à 0,89 en janvier et juillet, 0,93 à 0,95 en février, juin, août et décembre, 0,98 à 0,99 en mars, mai, septembre et novembre, 1,00 en avril et octobre ; le datacenter à 0,94, 0,96 à 0,97 et 0,98 à 0,99 aux mêmes mois. L'hôpital est à 0,94 aux creux (un jour par mois).
**ML.** Le mois est une variable (à traiter comme cyclique), l'année n'en est pas une. Il faut au moins un an d'historique pour que le modèle voie la saison.

### 6. Pas de jours fériés

**Preuve.** Bureau SITE001, 10 h à 17 h : 167,3 kW le 1er mai 2024 contre 166,0 le mercredi 8 mai ; 159,6 le 25 décembre contre 158,8 le 18 ; 150,1 le 1er janvier contre 149,8 en milieu de mois. Le dimanche 14/07/2024 suit le profil de week-end.
**ML.** Inutile d'ajouter un calendrier de jours fériés.

### 7. La température n'explique pas la consommation

**Constat.** La température du mock suit un cycle annuel décalé de trois mois et n'agit presque pas sur la consommation.
**Preuve.** Moyenne journalière (SITE001, mercredi de mi-mois) : 15,1 °C en janvier, 25,0 en avril, 15,1 en juillet, 5,0 en octobre. Cycle jour et nuit d'environ 4 °C de part et d'autre (janvier : 11,2 à 3 h, 18,7 à 9 h, 18,9 à 15 h, 11,6 à 21 h). Sur 12 dimanches (profil plat, 96 points par jour), corrélation avec la température de −0,03 à +0,02, avec l'écart à 15 °C de +0,13 à +0,28, soit une pente de 0,2 % à 0,4 % par degré. Sur 24 heures, la corrélation brute est élevée pour les bureaux, les usines et le commerce (0,73, 0,69 et 0,57 pour SITE001, SITE002 et SITE004) parce que température et activité suivent toutes deux le cycle jour et nuit ; après retrait de la moyenne horaire de chaque site elle tombe entre −0,07 et +0,02 (analyse exploratoire du 21 au 22/10, voir la dernière section).
**ML.** Ne pas attendre de gain de la température du mock, ni d'une météo réelle : elle n'explique pas des données simulées. L'information est dans le mois.
**ETL.** La stocker (8,5 % de valeurs manquantes) pour l'affichage.

### 8. `consumption_kwh` est égal à `consumption_kw`

**Preuve.** Égalité sur 49 000 lignes sur 49 000, nulls compris. La FAQ le confirme.
**ETL.** Ne pas créer la colonne `consumption_kwh` dans `core`. L'énergie se calcule : kW multipliés par la durée entre deux mesures.

### 9. Pics : `is_peak` à 80 % de la capacité est inutilisable

**Preuve.** Part des points au-dessus de 80 % de `capacity_kw` : 12 % à 18 % pour les bureaux, 36 % pour les usines, 40 % pour l'hôpital, **93 % pour le datacenter** (moyenne de 735 kW pour 800 de capacité). Maximum entre 0,94 et 1,11 fois la capacité, aucun pic spontané sur la semaine.
**ETL et ML.** Mesurer un pic par rapport au profil du site : écart supérieur à environ 15 % (3 écarts-types) au niveau attendu pour le site, le mois, le type de jour et l'heure. `POST /simulate/spike/{site_id}` est la seule source d'anomalies du mock (non testée).

### 10. Valeurs nulles et qualité

**Constat.** Les nulls arrivent par épisodes d'environ 45 secondes, sans motif horaire. `/current` en produit beaucoup plus que `/readings`.
**Preuve, `/readings`.** Semaine de mars 2024 : consommation manquante sur 5,7 % à 6,3 % des points, température sur 8,2 % à 8,9 %, humidité sur 7,6 % à 8,4 %. Qualité : 79 % `good`, 17,7 % `partial`, 1,4 % `degraded`, 2,0 % `critical`. `null_reasons` et `data_quality` sont cohérents sur les 49 000 lignes. Par tranche de quatre heures : 4,2 % à 6,0 % (deux sites, 1er au 7 juillet 2024). Au pas de 3,6 s sur une heure et 7 sites : 38 séries de 12 à 13 points (43 à 47 s), une de 25 (90 s). Au pas de 86 s : 364 séries d'un point, 21 de deux, 3 de trois.
**Preuve, `/current`.** Sur 1 heure (23/10/2026, 361 tours de 7 sites, un relevé toutes les 10 s) : consommation nulle dans 25,6 % des relevés (de 22 % à 30 % selon le site, soit environ 100 changements d'état par site) ; les états `partial`, `degraded` et `critical` reviennent par blocs de 5 relevés, soit environ 50 s ; la qualité évolue par séries (`good`, `partial`, `degraded`, `critical`). Une première mesure de 5 minutes donnait 30 %. Des appels en rafale retombent tous dans le même épisode (jusqu'à 100 % de nulls) : un test de charge ne mesure pas le taux réel.
**Preuve, `/sensors/status`.** Ce endpoint liste, par site, l'état de cinq capteurs (`consumption`, `electrical`, `temperature`, `humidity`, `network`) avec `status` (`ok` ou `failing`) et `failing_until`. Sur 95 pannes observées, il restait de 39 à 45 secondes avant `failing_until` au premier constat : une panne dure au plus environ 45 s. Les causes de `null_reasons` de `/current` sont identiques aux capteurs en panne dans 118 relevés sur 210 ; dans 74 autres, `/current` ne liste que `network_loss` alors que `/sensors/status` en liste davantage : une perte réseau masque les autres causes. Les écarts restants (18 relevés) tombent aux bornes des pannes. Par ailleurs `/stats/summary` renvoie en un appel la consommation instantanée et la qualité des 7 sites (nulle si le capteur est en panne).
**ETL.** Stocker les NULL tels que reçus et ne pas réessayer : une panne couvre 4 à 5 relevés à 10 s. Relever `/sensors/status` à chaque tour (un appel pour les 7 sites) et le conserver (`core.sensor_status` : site, capteur, début, `failing_until`) : c'est la seule source fiable des causes, `null_reasons` étant masqué par `network_loss`. Vue `analytics.latest_reading` : dernière consommation non nulle par site, son âge, et la qualité du tout dernier relevé.
**ML.** Exclure les NULL des moyennes et les lignes `critical` de l'entraînement ; ne pas imputer sur de longues plages. Le dataset de 7 000 lignes du 21 au 22/10 donne les causes déclarées : température 469, humidité 419, électrique 282, consommation 273, réseau 146.

### 11. Horodatage et fuseau

**Constat.** Le profil suit l'heure de l'horodatage renvoyé. Pour `/readings` cette heure est en UTC (les décalages sont convertis) ; pour `/current`, c'est l'horloge du mock, qui n'est pas stable.
**Preuve.** Mêmes 24 h de SITE001 demandées en naïf, en `+00:00`, en `Z` et en `+02:00` : la montée au-dessus de 110 kW tombe à 9 h dans les quatre cas, et la fenêtre en `+02:00` renvoie un premier horodatage à 22:00Z la veille (converti en UTC). Le 22/10, `/health` indiquait 10:50 pour 08:50 UTC (heure de Paris) ; le 23/10, `/current` indique 08:45:33 pour 08:45:49 UTC (UTC, 16 secondes d'écart). Le 23/10 à 08:45, la moyenne de `/current` pour SITE001 est de 85,7 kW, soit le niveau de 8 h (85,4 kW). Une fin de fenêtre postérieure à l'horloge du mock renvoie 400 (« dans le futur »), y compris une heure de Paris écrite en UTC.
**ETL.** Axe du temps d'un relevé `/current` : l'heure de réception en UTC (colonne `received_at`), l'horodatage du mock conservé à côté, et l'écart entre les deux consigné à chaque tour pour repérer un nouveau changement de fuseau. Fenêtres de rattrapage écrites en UTC. Stocker en `timestamptz`.
**ML.** Mélanger du rattrapage (heure UTC) et du flux courant quand le mock était à l'heure de Paris décalerait le profil de deux heures. Le 23/10 les deux concordent.

### 12. Alertes

**Preuve.** `/alerts` est indépendant des mesures (FAQ). Le 22/10, une alerte « risque de surcharge » du datacenter portait sur 774 kW avec un seuil de 630 kW, alors que ce site consomme ordinairement 735 kW sans alerte.
**ETL.** Stocker avec `origin = api` ; les alertes utiles sont celles que nous calculons (`origin = rule`).

### 13. Le courant est redondant avec la consommation

**Preuve.** Corrélation entre `consumption_kw` et `current_a` de 0,98 à 1,00 pour chaque site, contre −0,08 à +0,06 pour `voltage_v` et `power_factor` (analyse exploratoire du 21 au 22/10).
**ML.** Ne pas utiliser `current_a` (ni les grandeurs électriques mesurées au même instant) pour prévoir : elles dérivent de la cible et ne sont pas connues à l'avance.

### 14. Écarts avec le dataset 2023-2024

- Colonnes du dataset absentes du mock : `consumption_euros`, `solar_irradiance_wm2`. Colonnes du mock absentes du dataset : `voltage_v`, `current_a`, `power_factor`, `null_reasons`, `data_quality`.
- Sites nommés par type dans le dataset, par ville dans le mock (avec `capacity_kw`).
- Niveaux plus élevés au dataset (SITE001 : 112,7 kW contre 94 ; SITE002 : 617 contre 564), sur deux ans et non une semaine.
- Environ 350 anomalies étiquetées par site au dataset, aucune spontanée au mock. Nulls : 2,3 % au dataset contre environ 6 % au mock.

Le schéma de la base suit le mock. Le dataset ne sert que de référence de profils et de vérité terrain pour une détection d'anomalies.

## Conséquences pour le modèle de données (à valider par l'équipe)

1. `core.energy_reading` : pas de `consumption_kwh` ; clé (`time`, `site_id`) ; colonnes `source` (`current` ou `readings`) et `received_at` ; `timestamptz`.
2. `raw.api_response` : conservation courte, `raw_id` nullable en `ON DELETE SET NULL` (60 000 lignes par jour à 10 s, environ 13 000 à 60 s). La clé étrangère et le droit `DELETE` de l'ETL sur `raw` sont posés par la migration `20261025100000` ; **la purge elle-même n'est pas écrite** (tâche à ajouter au collecteur).
3. `analytics` : agrégats continus à la minute et à l'heure en temps réel, plus `latest_reading` (constat 10). `core.sensor_status` pour les pannes de capteur (constat 10).
4. `analytics.site_baseline` (site, mois, type de jour, heure, moyenne, écart-type, nombre de mesures), recalculée par l'ETL : sert à `is_peak`, aux alertes `rule` et de référence pour le ML.
5. Rattrapage : le profil étant déterministe, une grille d'une heure (environ 120 000 lignes pour deux ans et 7 sites) suffit à bâtir les profils ; 5 minutes (environ 1,5 million de lignes) seulement si le dashboard remonte l'historique à cette finesse.
6. `etl.run` avec un type de tâche (`poll_current`, `backfill`, `ref_load`) ; pour le collecteur, un résumé périodique et chaque échec.
7. `ref.tariff` pour le prix du kWh : 0,15 € constant (rapport euros/kWh du dataset 2023-2024 sur 118 015 lignes, écart maximal 0,0003 dû à l'arrondi, aucune variation par site, heure, jour ou mois), repris pour les mesures du mock, qui n'a pas de prix.
8. `core.alert.last_seen_at` et `resolved_at` (migration `20261025100100`) : l'ETL enregistre dans `last_seen_at` la dernière réception d'une alerte. **Les identifiants du mock ne sont pas stables** (le suffixe est l'heure de la requête, et la liste change à chaque appel, mesuré le 27/10) : une alerte ne disparaît jamais de la réponse, elle est remplacée. L'API déduit donc l'état de la fraîcheur : active si vue depuis moins de 15 minutes. `resolved_at` n'est pas utilisé.
9. `ml.history_labeled` (migration `20261025100300`) : l'historique 2023-2024 du jeu fourni, avec ses anomalies étiquetées (plateau, panne, chute, pic), pour la détection d'anomalies. Table à part, jamais mélangée à `core.energy_reading` : mêmes `site_id` et mêmes heures que le rattrapage du mock, mais des niveaux de 0 % à 30 % plus élevés selon le site (comparaison du 4 au 10 mars 2024). Le détecteur raisonne en écart au profil de chaque source, pas en kW bruts.

## Recoupement avec l'analyse exploratoire ML

Les notebooks 01 (24 h, du 21 au 22/10) et 02 (7 jours, du 15 au 22/10) de l'équipe ML, 7 000 mesures chacun, aboutissent aux mêmes constats que nos sondages indépendants :

- qualité : 78,8 % `good`, 17,7 % `partial`, 1,4 % `degraded`, 2,1 % `critical` (nous : 79 / 17,7 / 1,4 / 2,0) ; aucune ligne `good` avec valeur manquante ; consommation manquante sur 6,0 % (24 h) et 6,43 % (7 jours) ;
- `consumption_kwh` égal à `consumption_kw` sur 6 591 lignes comparables ; pas de 86,4 s (24 h, `limit=1000`) et de 604,8 s (7 jours), soit fenêtre divisée par `limit` ;
- week-end : usines −49 %, bureaux −28 % à −29 %, commerce +34,7 %, datacenter et hôpital inchangés ; coefficient de variation de 45 % à 48 % pour bureaux et usines, 5 % à 6 % pour datacenter et hôpital ;
- température : corrélation brute élevée qui s'annule une fois la moyenne horaire retirée.

Ce que nos sondages ajoutent : la saisonnalité mensuelle (le notebook 02 prévoit de l'étudier sur un an), l'absence de jours fériés, le bruit de 5 % et donc le plancher d'erreur, les pannes de capteur de 45 s et `/sensors/status`, le fuseau. Ce que les notebooks ajoutent et que nous retenons : le courant `current_a` redondant avec la cible (constat 13). Ils posent la question d'un effet de la température à l'échelle saisonnière : la réponse est non, le facteur du mois n'a pas besoin de la température (constat 7). Aucun constat des notebooks n'est contredit. Les notebooks sont dans un dossier local ; à versionner (par exemple `ml/notebooks/`).

## Non vérifié

- La saison est mesurée sur les 52 mercredis de 2024 (10 h à 17 h), pas sur tous les jours de l'année ni en week-end.
- Les nulls de `/current` sont mesurés sur une heure (26 %) ; l'écart avec `/readings` (6 % à 8 %) est stable mais n'est pas expliqué. À confirmer par le collecteur sur plusieurs jours, y compris la nuit et le week-end.
- `POST /simulate/spike/{site_id}` (paramètre `duration_minutes`, de 1 à 240) est documenté comme outil de test d'alertes et de détection, mais n'a pas été appelé : le mock est partagé, un pic risque d'être vu par les autres équipes. À faire avec l'accord de l'équipe, en notant l'heure.
- Changement d'heure du 25/10/2026 : l'historique du mock n'applique aucun changement d'heure (grille régulière d'une minute sans trou ni doublon le 30/03/2025 et le 26/10/2025), et l'horloge du mock est en UTC aujourd'hui. Rien ne doit se passer, à confirmer le jour même.
- Le 400 du premier essai n'a pas été reproduit tel quel ; la frontière est établie : toute fin de fenêtre postérieure à l'horloge du mock renvoie 400.
