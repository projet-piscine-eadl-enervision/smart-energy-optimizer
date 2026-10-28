// Commandes partagées par tous les scénarios.
// Les comptes sont créés par l'API réelle : chaque test utilise un email unique, ce qui évite
// de vider la base entre deux lancements.
import { ADMIN, DEFAULT_PASSWORD, TOKEN_KEY, uniqueEmail } from './helpers';

/** Crée un compte directement par l'API (plus rapide que par le formulaire). */
Cypress.Commands.add('createUser', (email, password = DEFAULT_PASSWORD) => {
  return cy.request('POST', '/api/auth/register', { email, password });
});

/** Récupère un jeton par l'API : /auth/login attend un formulaire, pas du JSON. */
Cypress.Commands.add('getToken', (email, password = DEFAULT_PASSWORD) => {
  return cy
    .request({
      method: 'POST',
      url: '/api/auth/login',
      form: true,
      body: { username: email, password },
    })
    .its('body.access_token');
});

/** Ouvre une page avec un jeton déjà en place, comme après une connexion. */
Cypress.Commands.add('visitAsLoggedIn', (path, token) => {
  return cy.visit(path, {
    onBeforeLoad(win) {
      win.localStorage.setItem(TOKEN_KEY, token);
    },
  });
});

/** Simule le profil renvoyé par /api/auth/me (rôle et site), avec le vrai email du compte. */
Cypress.Commands.add('stubAccount', (email, account) => {
  return cy.intercept('GET', '/api/auth/me', {
    id: 1,
    email,
    is_active: true,
    created_at: '2026-10-28T00:00:00Z',
    ...account,
  });
});

/**
 * Crée un compte neuf et ouvre une page en étant connecté avec ce compte.
 * `account` simule son profil (admin par défaut) ; `null` garde le vrai profil de l'API : un `user`
 * sans site.
 */
Cypress.Commands.add('loginAsNewUser', (path = '/', account = ADMIN) => {
  const email = uniqueEmail();
  return cy.createUser(email).then(() =>
    cy.getToken(email).then((token) => {
      if (account) cy.stubAccount(email, account);
      return cy.visitAsLoggedIn(path, token).then(() => email);
    })
  );
});

/** Remplit et envoie le formulaire de la page /login. */
Cypress.Commands.add('submitAuthForm', (email, password) => {
  cy.get('input[formcontrolname="email"]').clear().type(email);
  cy.get('input[formcontrolname="password"]').clear().type(password, { log: false });
  cy.get('button[type="submit"]').click();
});
