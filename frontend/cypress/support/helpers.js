// Valeurs et fonctions utilisées par les scénarios et par les commandes (support/e2e.js).
// Fichier séparé : importer support/e2e.js dans un scénario y enregistrerait les commandes deux fois.

// Même clé que dans src/app/core/auth.service.ts
export const TOKEN_KEY = 'enervision_token';
export const DEFAULT_PASSWORD = 'MotDePasse123';

/** Email jamais utilisé, pour créer un compte neuf à chaque test. */
export function uniqueEmail() {
  return `e2e-${Date.now()}-${Cypress._.random(1e6)}@enervision-e2e.fr`;
}
