-- migrate:up
-- Suivi de l'état des alertes. Le mock ne renvoie que les alertes actives : l'ETL déduira l'état
-- (active tant qu'elle figure dans la réponse, résolue quand elle disparaît).
-- Colonnes nullables : l'ETL actuel (INSERT avec liste de colonnes) continue de fonctionner.
-- Tant que l'ETL ne remplit pas ces colonnes, resolved_at est NULL pour toutes les alertes :
-- elles paraissent toutes actives, l'état n'a de sens qu'une fois l'ETL mis à jour.
ALTER TABLE core.alert ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;  -- dernier tour où elle figurait dans /alerts
ALTER TABLE core.alert ADD COLUMN IF NOT EXISTS resolved_at  TIMESTAMPTZ;  -- NULL : active ; sinon tour où elle a disparu

-- Lecture incrémentale (alertes depuis tel instant, tous sites confondus) pour l'API et le tableau de bord.
CREATE INDEX IF NOT EXISTS ix_alert_time ON core.alert (time DESC);
-- migrate:down
