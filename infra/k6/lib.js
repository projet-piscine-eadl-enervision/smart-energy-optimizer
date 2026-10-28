// Outils communs aux scénarios k6 : garde-fou sur la cible, connexion, paramètres des requêtes.
//
// Variables d'environnement :
//   BASE_URL     URL de l'API testée (http://localhost:8000 par défaut, http://api:8000 depuis le compose)
//   K6_EMAIL     compte de test (admin, ou user rattaché à un site), jamais versionné
//   K6_PASSWORD  mot de passe de ce compte
import http from 'k6/http';
import { check, fail, sleep } from 'k6';

function trimTrailingSlashes(url) {
  let end = url.length;
  while (end > 0 && url[end - 1] === '/') {
    end--;
  }
  return url.slice(0, end);
}

export const BASE_URL = trimTrailingSlashes(__ENV.BASE_URL || 'http://localhost:8000');

// Hôtes de la production (CloudFront devant l'EC2) : jamais de test de charge dessus
const FORBIDDEN_HOSTS = [/\.cloudfront\.net$/i, /\.amazonaws\.com$/i];

// Attente de l'API au démarrage : 30 essais espacés de 2 s, soit une minute au plus
const HEALTH_RETRIES = 30;

export function targetHost(url) {
  const match = /^https?:\/\/([^/:?#]+)/i.exec(url);
  return match ? match[1].toLowerCase() : null;
}

/**
 * Refuse de lancer la charge contre la production : hôte AWS connu, ou API qui se déclare
 * en production dans /health. À appeler dans setup(), avant toute autre requête.
 */
export function guardTarget() {
  const host = targetHost(BASE_URL);
  if (!host) {
    fail(`BASE_URL invalide : « ${BASE_URL} »`);
  }
  if (FORBIDDEN_HOSTS.some((pattern) => pattern.test(host))) {
    fail(`Cible refusée : ${host} est un hôte de production`);
  }
  // L'API peut être en train de démarrer : `docker compose run` la recrée quand le .env a changé
  let response = http.get(`${BASE_URL}/health`, { tags: { name: '/health' } });
  for (let attempt = 1; response.status !== 200 && attempt <= HEALTH_RETRIES; attempt++) {
    sleep(2);
    response = http.get(`${BASE_URL}/health`, { tags: { name: '/health' } });
  }
  if (response.status !== 200) {
    fail(`API injoignable sur ${BASE_URL}/health (statut ${response.status})`);
  }
  const environment = response.json('environment');
  if (environment === 'production') {
    fail('Cible refusée : l\'API se déclare en production');
  }
  return environment;
}

/** Connexion du compte de test : renvoie le jeton. Une seule fois par test, pas par itération. */
export function login() {
  const email = __ENV.K6_EMAIL;
  const password = __ENV.K6_PASSWORD;
  if (!email || !password) {
    fail('K6_EMAIL et K6_PASSWORD sont obligatoires (compte de test, hors du dépôt)');
  }
  const response = http.post(
    `${BASE_URL}/auth/login`,
    { username: email, password },
    { tags: { name: '/auth/login' } },
  );
  if (!check(response, { 'login : 200': (r) => r.status === 200 })) {
    fail(`Connexion refusée pour le compte de test (statut ${response.status})`);
  }
  return response.json('access_token');
}

/** Paramètres d'une requête authentifiée, regroupée sous le nom de sa route dans les résultats. */
export function authParams(token, name) {
  return {
    headers: { Authorization: `Bearer ${token}` },
    tags: { name },
  };
}
