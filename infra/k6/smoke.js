// Scénario smoke : quelques utilisateurs qui ouvrent le tableau de bord en boucle pendant une minute.
// Lancé par la CI (job load) sur une pile éphémère. Échoue (code 99) si un seuil n'est pas tenu :
// aucune erreur acceptée, p95 sous P95_MS millisecondes.
//
// Variables : BASE_URL, K6_EMAIL, K6_PASSWORD (voir lib.js), et pour régler le test :
//   VUS (5)   DURATION (1m)   P95_MS (500)
// Usage local, pile démarrée : docker compose --profile load run --rm k6
import http from 'k6/http';
import { check, sleep } from 'k6';

import { BASE_URL, authParams, guardTarget, login } from './lib.js';

const P95_MS = Number(__ENV.P95_MS || 500);

// Routes appelées par le tableau de bord, avec leurs paramètres par défaut
const ROUTES = [
  ['/sites', '/sites'],
  ['/history', '/history?days=7'],
  ['/predictions', '/predictions?hours=24'],
  ['/recommendations', '/recommendations'],
  ['/alerts', '/alerts'],
];

export const options = {
  // setup() peut attendre jusqu'à une minute que l'API démarre (lib.js)
  setupTimeout: '2m',
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: Number(__ENV.VUS || 5),
      duration: __ENV.DURATION || '1m',
    },
  },
  // Les seuils ne portent que sur le scénario : la connexion de setup() (bcrypt, lent exprès) est à part
  thresholds: {
    'http_req_failed{scenario:smoke}': ['rate==0'],
    'http_req_duration{scenario:smoke}': [`p(95)<${P95_MS}`],
    checks: ['rate==1'],
    // Une ligne par route dans le résumé, pour voir laquelle ralentit
    ...Object.fromEntries(
      ROUTES.map(([name]) => [`http_req_duration{scenario:smoke,name:${name}}`, [`p(95)<${P95_MS}`]]),
    ),
  },
};

export function setup() {
  const environment = guardTarget();
  console.log(`Cible : ${BASE_URL} (environnement ${environment})`);
  return { token: login() };
}

export default function (data) {
  for (const [name, path] of ROUTES) {
    const response = http.get(`${BASE_URL}${path}`, authParams(data.token, name));
    check(response, { [`${name} : 200`]: (r) => r.status === 200 });
  }
  // Un utilisateur relit son tableau de bord environ chaque seconde
  sleep(1);
}
