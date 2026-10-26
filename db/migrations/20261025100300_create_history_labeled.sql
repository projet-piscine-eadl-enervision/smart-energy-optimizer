-- migrate:up
-- Historique 2023-2024 du jeu fourni (parquet nettoyé par l'ETL), avec ses anomalies étiquetées.
-- Table séparée de core.energy_reading : les deux sources ont les mêmes site_id et les mêmes heures
-- mais des niveaux différents (de 0 % à 30 % d'écart selon le site) ; la clé (site_id, time) ferait
-- écarter l'une des deux sans erreur. Ne sert qu'à la détection d'anomalies, hors analytics.
CREATE TABLE IF NOT EXISTS ml.history_labeled (
    site_id              TEXT        NOT NULL REFERENCES ref.site (site_id),
    time                 TIMESTAMPTZ NOT NULL,        -- heure de la grille du jeu fourni (UTC)
    consumption_kw       NUMERIC,                     -- consommation nettoyée (kW moyen sur l'heure)
    consumption_source   TEXT        NOT NULL
                           CHECK (consumption_source IN ('measured', 'interpolated', 'recovered_from_euros', 'missing')),
    temperature_celsius  NUMERIC,
    humidity_percent     NUMERIC,
    solar_irradiance_wm2 NUMERIC,
    anomaly_type         TEXT REFERENCES ref.alert_type (alert_type),   -- NULL : aucune anomalie étiquetée
    anomaly_severity     TEXT REFERENCES ref.severity (severity),
    PRIMARY KEY (site_id, time),
    CHECK ((anomaly_type IS NULL) = (anomaly_severity IS NULL))
);

-- L'ETL charge la table. Le ML et l'API la lisent grâce aux droits par défaut du schéma ml.
GRANT USAGE ON SCHEMA ml TO enervision_etl;
GRANT SELECT, INSERT, UPDATE ON ml.history_labeled TO enervision_etl;
-- migrate:down
