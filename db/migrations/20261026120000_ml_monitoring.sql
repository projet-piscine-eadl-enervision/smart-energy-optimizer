-- migrate:up
-- Suivi du modèle, lisible en SQL (Grafana, API) sans passer par MLflow.
-- Le ML écrit les tables à chaque entraînement ; les vues comparent ml.prediction à la mesure réelle.
-- Droits : ceux par défaut du schéma ml (le ML écrit, l'API lit).

-- Un entraînement par version MLflow du modèle enervision-consumption
CREATE TABLE IF NOT EXISTS ml.model_run (
    model_version        TEXT PRIMARY KEY,            -- version MLflow, comme ml.prediction.model_version
    run_id               TEXT NOT NULL,               -- run MLflow (paramètres, données, artefacts)
    model                TEXT NOT NULL,               -- site_profile, seasonal_naive…
    trained_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    train_start          TIMESTAMPTZ NOT NULL,
    train_end            TIMESTAMPTZ NOT NULL,
    promoted             BOOLEAN NOT NULL,            -- devenu champion à l'entraînement
    decision             TEXT NOT NULL,               -- explication de la promotion
    shiftable_ratio      NUMERIC NOT NULL,            -- hypothèses du processus métier simulé
    peak_penalty_eur_kwh NUMERIC NOT NULL             -- (ml/enervision_ml/config.py)
);

-- Métriques de l'entraînement : val_nmae, test_nmae, test_kpi_penalty_saved_eur, test_nmae_gain_vs_naive…
CREATE TABLE IF NOT EXISTS ml.model_metric (
    model_version TEXT NOT NULL REFERENCES ml.model_run (model_version) ON DELETE CASCADE,
    metric        TEXT NOT NULL,
    value         DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (model_version, metric)
);

-- Seuil de pic de chaque site, propre à une version (1,25 × moyenne de son entraînement)
CREATE TABLE IF NOT EXISTS ml.peak_threshold (
    model_version TEXT NOT NULL REFERENCES ml.model_run (model_version) ON DELETE CASCADE,
    site_id       TEXT NOT NULL REFERENCES ref.site (site_id),
    threshold_kw  NUMERIC NOT NULL,
    PRIMARY KEY (model_version, site_id)
);

-- Chaque prévision passée face à la mesure réelle. Une heure dont plus de la moitié des mesures
-- n'ont pas de consommation est écartée, comme à l'entraînement (features.mask_unreliable_hours).
-- Le dépassement évité suit evaluate.business_kpis : sur une heure annoncée en pic, la part décalable
-- de la consommation efface le dépassement réel, dans la limite de ce dépassement.
CREATE OR REPLACE VIEW ml.prediction_vs_actual AS
SELECT
    p.target_time,
    p.site_id,
    p.model_version,
    p.predicted_at,
    p.predicted_kw::float                                         AS predicted_kw,
    h.avg_consumption_kw::float                                   AS actual_kw,
    abs(p.predicted_kw - h.avg_consumption_kw)::float             AS abs_error_kw,
    t.threshold_kw::float                                         AS threshold_kw,
    p.is_peak,
    h.avg_consumption_kw > t.threshold_kw                         AS actual_peak,
    least(greatest(h.avg_consumption_kw - t.threshold_kw, 0),
          r.shiftable_ratio * h.avg_consumption_kw)::float        AS peak_kwh_avoidable,
    CASE WHEN p.is_peak
         THEN least(greatest(h.avg_consumption_kw - t.threshold_kw, 0),
                    r.shiftable_ratio * h.avg_consumption_kw)
         ELSE 0 END::float                                        AS peak_kwh_avoided,
    r.peak_penalty_eur_kwh::float                                 AS peak_penalty_eur_kwh
FROM ml.prediction p
JOIN analytics.energy_hourly h ON h.hour = p.target_time AND h.site_id = p.site_id
LEFT JOIN ml.model_run r ON r.model_version = p.model_version
LEFT JOIN ml.peak_threshold t ON t.model_version = p.model_version AND t.site_id = p.site_id
WHERE h.avg_consumption_kw IS NOT NULL
  AND h.nb_missing <= 0.5 * h.nb_readings;

-- Qualité et impact par jour (heure de Paris, comme analytics.energy_daily), site et version.
-- nmae : erreur moyenne rapportée à la consommation moyenne ; moyenne des sites dans Grafana.
CREATE OR REPLACE VIEW ml.prediction_quality_daily AS
SELECT
    time_bucket(INTERVAL '1 day', target_time, 'Europe/Paris')    AS day,
    site_id,
    model_version,
    count(*)                                                      AS nb_hours,
    avg(abs_error_kw)                                             AS mae_kw,
    avg(abs_error_kw) / nullif(avg(actual_kw), 0)                 AS nmae,
    count(*) FILTER (WHERE is_peak AND actual_peak)               AS peak_hours_announced,
    count(*) FILTER (WHERE actual_peak AND NOT is_peak)           AS missed_peak_hours,
    count(*) FILTER (WHERE is_peak AND NOT actual_peak)           AS false_alarm_hours,
    sum(peak_kwh_avoided)                                         AS peak_kwh_avoided,
    sum(peak_kwh_avoided) / nullif(sum(peak_kwh_avoidable), 0)    AS peak_avoided_ratio,
    sum(peak_kwh_avoided * peak_penalty_eur_kwh)                  AS penalty_saved_eur
FROM ml.prediction_vs_actual
GROUP BY day, site_id, model_version;

-- Fraîcheur : la prédiction tourne toutes les heures ; un âge de plus de deux heures signale une panne
CREATE OR REPLACE VIEW ml.prediction_freshness AS
SELECT
    site_id,
    (array_agg(model_version ORDER BY predicted_at DESC))[1]      AS model_version,
    max(predicted_at)                                             AS last_predicted_at,
    now() - max(predicted_at)                                     AS age,
    max(target_time)                                              AS last_target_time
FROM ml.prediction
GROUP BY site_id;
-- migrate:down
