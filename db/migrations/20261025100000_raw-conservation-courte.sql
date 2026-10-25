-- migrate:up
-- Conservation courte de raw.api_response (environ 13 000 réponses par jour avec le collecteur à 60 s).
-- Sans ON DELETE, supprimer une réponse déjà citée par une mesure est refusé : la purge est impossible.
-- Avec SET NULL, la mesure garde ses valeurs et perd seulement le lien vers la réponse brute.
ALTER TABLE core.energy_reading DROP CONSTRAINT IF EXISTS energy_reading_raw_id_fkey;
ALTER TABLE core.energy_reading ADD CONSTRAINT energy_reading_raw_id_fkey
    FOREIGN KEY (raw_id) REFERENCES raw.api_response (id) ON DELETE SET NULL;

-- Sans cet index, chaque réponse supprimée parcourrait toute l'hypertable pour mettre raw_id à NULL.
CREATE INDEX IF NOT EXISTS ix_energy_reading_raw_id
    ON core.energy_reading (raw_id) WHERE raw_id IS NOT NULL;

-- Le droit de supprimer n'est accordé que sur raw : core, ref et etl restent sans DELETE.
GRANT DELETE ON ALL TABLES IN SCHEMA raw TO enervision_etl;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT DELETE ON TABLES TO enervision_etl;
-- migrate:down
