-- migrate:up
-- Fin du jeu de données de l'entraînement (ML_DATA_END, ou minuit UTC du jour) : elle fixe les
-- fenêtres de validation et de test, donc la comparaison entre deux versions. Vide pour les
-- versions entraînées avant cette colonne.
ALTER TABLE ml.model_run ADD COLUMN IF NOT EXISTS data_end TIMESTAMPTZ;

-- migrate:down
