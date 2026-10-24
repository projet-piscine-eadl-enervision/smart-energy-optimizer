# Étapes :
# - dev   : serveur de développement Angular, utilisé par docker-compose.yml (target: dev)
# - build : compilation de production
# - prod  : serveur SSR Node, qui transmet aussi /api/ à l'API (variable API_UPSTREAM, lue au
#           lancement). Image publiée par la CI : la même pour le staging et la production
#           (étape par défaut)

FROM node:24-slim AS base

# Hôtes acceptés par le rendu SSR d'Angular (protection SSRF)
ENV NG_ALLOWED_HOSTS=localhost,127.0.0.1

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

FROM base AS dev

RUN chown -R node:node /app
USER node

EXPOSE 4000

CMD ["npx", "ng", "serve", "--host", "0.0.0.0", "--port", "4000", "--poll", "1000"]

FROM base AS build

RUN npm run build

FROM node:24-slim AS prod

# Variables lues au lancement, jamais à la construction : la même image sert en staging et en
# production.
# - NG_ALLOWED_HOSTS : nom ou IP sous lesquels le site est joint (VM en staging, adresse AWS en production)
# - API_UPSTREAM : adresse de l'API vers laquelle le serveur transmet /api/ (voir src/server.ts)
ENV NODE_ENV=production \
    NG_ALLOWED_HOSTS=localhost,127.0.0.1 \
    API_UPSTREAM=http://api:8000 \
    PORT=4000

# npm, npx, corepack et yarn sont inutiles à l'exécution : le serveur est dans dist/. Retirés, ils ne
# laissent plus leurs dépendances embarquées (brace-expansion, undici) déclencher des alertes Trivy.
RUN rm -rf /usr/local/lib/node_modules /usr/local/bin/npm /usr/local/bin/npx \
        /usr/local/bin/corepack /usr/local/bin/yarn /usr/local/bin/yarnpkg /opt/yarn-*

WORKDIR /app

COPY --from=build --chown=node:node /app/dist ./dist

USER node

EXPOSE 4000

# Sonde d'état : toute réponse inférieure à 500 prouve que le serveur répond (un 400 du contrôle
# d'hôte SSR reste acceptable si NG_ALLOWED_HOSTS ne contient pas 127.0.0.1)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:'+(process.env.PORT||4000)+'/').then(r=>process.exit(r.status<500?0:1)).catch(()=>process.exit(1))"]

CMD ["node", "dist/enervision/server/server.mjs"]
