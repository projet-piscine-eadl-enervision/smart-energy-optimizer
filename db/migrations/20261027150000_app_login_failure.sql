-- migrate:up
-- Échecs de connexion à /auth/login, lus par l'API pour limiter la force brute (api/app/core/login_throttle.py).
-- En base et non en mémoire : les compteurs restent communs à toutes les instances de l'API.
-- email_key est un HMAC de l'e-mail saisi (clé SECRET_KEY) : la table ne contient aucune adresse en clair,
-- et un e-mail inconnu a sa ligne comme un compte existant. L'API supprime elle-même les lignes expirées.
-- Une connexion réussie vide email_key des échecs de ce compte, sans les retirer du compteur de l'IP.
CREATE TABLE IF NOT EXISTS app.login_failure (
    login_failure_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ip                TEXT NOT NULL,
    email_key         TEXT,  -- NULL après une connexion réussie : l'échec ne compte plus que pour l'IP
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_login_failure_ip_created_at ON app.login_failure (ip, created_at);
CREATE INDEX IF NOT EXISTS ix_login_failure_email_key_created_at ON app.login_failure (email_key, created_at);
CREATE INDEX IF NOT EXISTS ix_login_failure_created_at ON app.login_failure (created_at);

-- Les droits par défaut du schéma app ne comprennent pas DELETE : la purge en a besoin
GRANT SELECT, INSERT, UPDATE, DELETE ON app.login_failure TO enervision_api;

-- E-mails en minuscules : l'API les normalise désormais à l'inscription et à la connexion.
-- Une adresse dont la version en minuscules existe déjà n'est pas modifiée (index unique) : elle est signalée,
-- à régler à la main.
UPDATE public.users AS u
SET email = lower(u.email)
WHERE u.email <> lower(u.email)
  AND NOT EXISTS (
      SELECT 1 FROM public.users AS other
      WHERE other.id <> u.id AND lower(other.email) = lower(u.email)
  );

DO $$
DECLARE
    duplicates INT;
BEGIN
    SELECT count(*) INTO duplicates FROM public.users WHERE email <> lower(email);
    IF duplicates > 0 THEN
        RAISE NOTICE '% compte(s) en double à la casse près, laissés tels quels : à fusionner à la main', duplicates;
    END IF;
END $$;
-- migrate:down
