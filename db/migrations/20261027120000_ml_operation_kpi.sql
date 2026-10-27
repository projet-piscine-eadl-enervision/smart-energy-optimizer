-- migrate:up
-- Indicateurs d'exploitation du modèle, lisibles en SQL (Grafana, API) : l'impact mesuré sur les 7 derniers
-- jours, et la couverture des prévisions à venir. Les hypothèses du processus simulé (part décalable, tarif)
-- sont celles de ml/enervision_ml/config.py, copiées dans ml.model_run à chaque entraînement.

-- Impact sur 7 jours glissants, par site : dépassement évité face à la mesure réelle et économie en euros
CREATE OR REPLACE VIEW ml.operation_kpi AS
SELECT
    site_id,
    sum(nb_hours)                  AS nb_hours,
    avg(nmae)                      AS nmae,
    sum(peak_kwh_avoided)          AS peak_kwh_avoided,
    sum(penalty_saved_eur)         AS penalty_saved_eur
FROM ml.prediction_quality_daily
WHERE day >= now() - interval '7 days'
GROUP BY site_id;

-- Automatisation : part des 24 prochaines heures qui ont une prévision (1 : couverture complète)
CREATE OR REPLACE VIEW ml.forecast_coverage AS
SELECT
    site_id,
    count(DISTINCT target_time) FILTER (
        WHERE target_time >= date_trunc('hour', now())
          AND target_time <  date_trunc('hour', now()) + interval '24 hours'
    )::float / 24                  AS coverage_next_24h
FROM ml.prediction
GROUP BY site_id;
-- migrate:down
