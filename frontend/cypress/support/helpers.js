// Valeurs et fonctions utilisées par les scénarios et par les commandes (support/e2e.js).
// Fichier séparé : importer support/e2e.js dans un scénario y enregistrerait les commandes deux fois.

// Même clé que dans src/app/core/auth.service.ts
export const TOKEN_KEY = 'enervision_token';
export const DEFAULT_PASSWORD = 'MotDePasse123';

/**
 * Profils simulés pour /api/auth/me. Un compte créé par l'API est un `user` sans site : il ne voit que
 * le message « Aucun site ». Les scénarios des écrans de données simulent donc un admin (tous les
 * sites) ou un user rattaché à un site ; les données elles-mêmes sont simulées par cy.intercept.
 */
export const ADMIN = { role: 'admin', site_id: null };
export const USER_SITE001 = { role: 'user', site_id: 'SITE001' };

/** Email jamais utilisé, pour créer un compte neuf à chaque test. */
export function uniqueEmail() {
  return `e2e-${Date.now()}-${Cypress._.random(1e6)}@enervision-e2e.fr`;
}
