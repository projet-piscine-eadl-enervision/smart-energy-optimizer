// Commandes partagées par tous les scénarios.
// Les comptes sont créés par l'API réelle : chaque test utilise un email unique, ce qui évite
// de vider la base entre deux lancements.
import { DEFAULT_PASSWORD, TOKEN_KEY, uniqueEmail } from './helpers';

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

/** Crée un compte neuf et ouvre une page en étant connecté avec ce compte. */
Cypress.Commands.add('loginAsNewUser', (path = '/') => {
  const email = uniqueEmail();
  return cy.createUser(email).then(() =>
    cy.getToken(email).then((token) => cy.visitAsLoggedIn(path, token).then(() => email))
  );
});

/** Remplit et envoie le formulaire de la page /login. */
Cypress.Commands.add('submitAuthForm', (email, password) => {
  cy.get('input[formcontrolname="email"]').clear().type(email);
  cy.get('input[formcontrolname="password"]').clear().type(password, { log: false });
  cy.get('button[type="submit"]').click();
});
