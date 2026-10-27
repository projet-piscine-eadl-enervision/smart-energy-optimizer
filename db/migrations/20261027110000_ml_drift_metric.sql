-- migrate:up
-- Surveillance du modèle en service (ml/enervision_ml/monitor.py), lisible en SQL (Grafana, API).
-- Chaque contrôle garde sa valeur, son seuil et son statut : ok, alert, ou insufficient (pas assez de
-- données pour conclure). Les droits par défaut du schéma ml donnent l'écriture au ML et la lecture à l'API.
CREATE TABLE IF NOT EXISTS ml.drift_metric (
    checked_at     TIMESTAMPTZ NOT NULL,
    model_version  TEXT NOT NULL REFERENCES ml.model_run (model_version) ON DELETE CASCADE,
    site_id        TEXT NOT NULL REFERENCES ref.site (site_id),
    metric         TEXT NOT NULL,      -- level_bias, outlier_share, missing_share, nmae_ratio, prediction_age_hours
    value          DOUBLE PRECISION,   -- vide quand le statut est insufficient
    threshold      DOUBLE PRECISION NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('ok', 'alert', 'insufficient')),
    PRIMARY KEY (checked_at, model_version, site_id, metric)
);

-- Dernier contrôle de chaque (site, indicateur)
CREATE OR REPLACE VIEW ml.model_health AS
SELECT DISTINCT ON (site_id, metric)
    site_id, metric, value, threshold, status, checked_at, model_version
FROM ml.drift_metric
ORDER BY site_id, metric, checked_at DESC;

-- État d'ensemble : alert dès qu'un indicateur est en alerte ; insufficient tant que rien ne permet de conclure
CREATE OR REPLACE VIEW ml.model_status AS
SELECT
    CASE WHEN count(*) = 0                              THEN 'insufficient'
         WHEN bool_or(status = 'alert')                 THEN 'alert'
         WHEN bool_and(status = 'insufficient')         THEN 'insufficient'
         ELSE 'ok' END                                  AS status,
    count(*) FILTER (WHERE status = 'alert')            AS nb_alerts,
    count(*) FILTER (WHERE status = 'insufficient')     AS nb_insufficient,
    max(checked_at)                                     AS checked_at
FROM ml.model_health;
-- migrate:down
