-- migrate:up
-- Site de rattachement d'un compte. Un compte `admin` lit tous les sites ; un compte `user` ne lit que
-- le sien. Vide par défaut : un `user` sans site n'a accès à aucune donnée tant qu'un admin ne lui en
-- attribue pas (voir api/README.md).
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS site_id TEXT REFERENCES ref.site (site_id);
CREATE INDEX IF NOT EXISTS ix_users_site_id ON public.users (site_id);

-- migrate:down
