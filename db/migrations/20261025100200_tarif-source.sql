-- migrate:up
-- Précise l'origine du tarif posé à la création de ref.tariff. La condition sur l'ancien texte évite
-- d'écraser une correction faite à la main.
UPDATE ref.tariff
SET source = 'Mesuré sur le jeu historique 2023-2024 : rapport euros/kWh constant à 0,15 sur 118 015 lignes '
             '(écart maximal 0,0003, dû à l''arrondi des euros), sans variation selon le site, l''heure, '
             'le jour ni le mois. Tarif plat, repris pour les mesures du mock, qui n''a pas de prix.'
WHERE valid_from = '2023-01-01' AND source = 'Mesuré sur le jeu historique';
-- migrate:down
