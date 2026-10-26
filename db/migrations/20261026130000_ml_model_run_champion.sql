-- migrate:up
-- Champion actuel dans ml.model_run : `promoted` dit seulement si la version est devenue champion
-- à son entraînement, il reste vrai pour les anciens champions. is_champion désigne la version
-- en service (alias champion de MLflow), mise à jour à chaque entraînement.
ALTER TABLE ml.model_run ADD COLUMN IF NOT EXISTS is_champion BOOLEAN NOT NULL DEFAULT false;

-- Au plus un champion
CREATE UNIQUE INDEX IF NOT EXISTS ux_model_run_champion ON ml.model_run (is_champion) WHERE is_champion;
-- migrate:down
