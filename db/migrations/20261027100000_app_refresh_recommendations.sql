-- migrate:up
-- Recommandations déduites des prévisions du ML et des alertes.
-- Un conseil (ref.recommendation_type) dépend du type de site et du type d'alerte qui le déclenche ;
-- app.recommendation en garde une ligne par conseil, site et heure.
--
-- Pics prévus (règle 'threshold') : la dernière prévision écrite pour chaque (site, heure) fait foi.
-- L'avenir est donc recalculé à chaque appel (un pic annulé par une prévision plus récente disparaît),
-- le passé est conservé : c'est l'historique des conseils donnés.
-- Alertes des dernières 24 h : une ligne par heure d'alerte, la clé d'unicité écarte les doublons.
--
-- Fonction exécutée avec les droits de son créateur, comme analytics.refresh_site_baseline() : le ML
-- l'appelle sans avoir le droit d'écrire dans le schéma app.
CREATE OR REPLACE FUNCTION app.refresh_recommendations()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    created integer := 0;
    added   integer;
BEGIN
    DELETE FROM app.recommendation r
    USING ref.recommendation_type t
    WHERE t.recommendation_type_id = r.recommendation_type_id
      AND t.trigger_rule = 'threshold'
      AND r.target_time >= date_trunc('hour', now());

    INSERT INTO app.recommendation (recommendation_type_id, site_id, target_time)
    SELECT t.recommendation_type_id, l.site_id, l.target_time
    FROM (
        SELECT DISTINCT ON (site_id, target_time) site_id, target_time, is_peak
        FROM ml.prediction
        WHERE target_time >= date_trunc('hour', now())
        ORDER BY site_id, target_time, predicted_at DESC
    ) l
    JOIN ref.site s ON s.site_id = l.site_id
    JOIN ref.recommendation_type t
      ON t.trigger_rule = 'threshold' AND (t.site_type = s.site_type OR t.site_type IS NULL)
    WHERE l.is_peak
    ON CONFLICT (recommendation_type_id, site_id, target_time) DO NOTHING;
    GET DIAGNOSTICS added = ROW_COUNT;
    created := created + added;

    INSERT INTO app.recommendation (recommendation_type_id, site_id, target_time)
    SELECT t.recommendation_type_id, a.site_id, date_trunc('hour', a.time)
    FROM core.alert a
    JOIN ref.site s ON s.site_id = a.site_id
    JOIN ref.recommendation_type t
      ON t.trigger_rule = a.alert_type AND (t.site_type = s.site_type OR t.site_type IS NULL)
    WHERE a.time >= now() - interval '24 hours'
    ON CONFLICT (recommendation_type_id, site_id, target_time) DO NOTHING;
    GET DIAGNOSTICS added = ROW_COUNT;
    created := created + added;

    RETURN created;
END;
$$;

-- Le ML n'a que le droit de traverser le schéma app (USAGE) et d'appeler la fonction : aucun droit sur les tables
GRANT USAGE ON SCHEMA app TO enervision_ml;
REVOKE ALL ON FUNCTION app.refresh_recommendations() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.refresh_recommendations() TO enervision_ml;
-- migrate:down
