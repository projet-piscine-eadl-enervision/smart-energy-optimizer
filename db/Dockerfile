# Applique les migrations de la base (dbmate). Une image publiée par la CI comme les autres modules :
# les migrations voyagent avec l'image, donc un retour arrière du staging ou de la production
# lance l'ancien jeu de migrations, déjà appliqué, et ne change rien.
FROM ghcr.io/amacneil/dbmate:2.38.0

# Utilisateur non-root pour exécuter les migrations
RUN addgroup -S -g 1000 app \
    && adduser -S -u 1000 -G app -H app

COPY --chown=app:app migrations /db/migrations

# Réglages de dbmate : attendre la base, ne pas écrire de fichier de schéma, verrou contre deux
# exécutions simultanées (le minuteur du staging relance la pile toutes les 2 minutes).
# DATABASE_URL est fournie par le compose.
ENV DBMATE_MIGRATIONS_DIR=/db/migrations \
    DBMATE_NO_DUMP_SCHEMA=true \
    DBMATE_WAIT=true \
    DBMATE_MIGRATION_LOCK=true

USER app

CMD ["up"]
