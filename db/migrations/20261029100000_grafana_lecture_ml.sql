-- migrate:up
-- Grafana : lecture seule du suivi du modèle (ml) et des sites (ref), pour le dashboard ML.
-- Rôle de groupe sans connexion ; le compte de connexion de Grafana se crée hors dépôt et en hérite.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'enervision_grafana_ml') THEN
        CREATE ROLE enervision_grafana_ml NOLOGIN; END IF;
END $$;

GRANT USAGE ON SCHEMA ml, ref TO enervision_grafana_ml;
GRANT SELECT ON ALL TABLES IN SCHEMA ml, ref TO enervision_grafana_ml;
-- Tables et vues créées par les prochaines migrations : même droit automatiquement
ALTER DEFAULT PRIVILEGES IN SCHEMA ml, ref GRANT SELECT ON TABLES TO enervision_grafana_ml;
-- migrate:down
