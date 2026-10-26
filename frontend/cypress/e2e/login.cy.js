import { DEFAULT_PASSWORD, TOKEN_KEY, uniqueEmail } from '../support/helpers';

describe('Connexion', () => {
  beforeEach(() => {
    cy.visit('/login');
  });

  it('affiche le formulaire de connexion', () => {
    cy.contains('h1', 'Connexion');
    cy.get('input[formcontrolname="email"]').should('be.visible');
    cy.get('input[formcontrolname="password"]').should('have.attr', 'type', 'password');
    cy.contains('button[type="submit"]', 'Se connecter');
  });

  it('connecte un utilisateur existant et ouvre le tableau de bord', () => {
    const email = uniqueEmail();
    cy.createUser(email);

    cy.submitAuthForm(email, DEFAULT_PASSWORD);

    cy.location('pathname').should('eq', '/');
    cy.contains('header', email);
    cy.window().its('localStorage').invoke('getItem', TOKEN_KEY).should('be.a', 'string');
  });

  it('refuse un mauvais mot de passe', () => {
    const email = uniqueEmail();
    cy.createUser(email);

    cy.submitAuthForm(email, 'MauvaisMotDePasse');

    cy.contains('Email ou mot de passe incorrect.');
    cy.location('pathname').should('eq', '/login');
    cy.window().its('localStorage').invoke('getItem', TOKEN_KEY).should('be.null');
  });

  it('refuse un email inconnu', () => {
    cy.submitAuthForm(uniqueEmail(), DEFAULT_PASSWORD);

    cy.contains('Email ou mot de passe incorrect.');
    cy.location('pathname').should('eq', '/login');
  });

  it("vérifie le formulaire avant d'appeler l'API", () => {
    cy.intercept('POST', '/api/auth/login').as('loginRequest');

    cy.get('input[formcontrolname="email"]').type('pas-un-email');
    cy.get('input[formcontrolname="password"]').type('court');
    cy.get('button[type="submit"]').click();

    cy.contains('Email invalide.');
    cy.contains('8 caractères minimum.');
    cy.location('pathname').should('eq', '/login');
    // Aucune requête ne doit partir avec un formulaire invalide
    cy.get('@loginRequest.all').should('have.length', 0);
  });

  it("prévient quand l'API est injoignable", () => {
    cy.intercept('POST', '/api/auth/login', { forceNetworkError: true });

    cy.submitAuthForm(uniqueEmail(), DEFAULT_PASSWORD);

    cy.contains("Impossible de joindre l'API");
  });

  it('déconnecte et revient à la page de connexion', () => {
    cy.loginAsNewUser('/');
    cy.contains('h2', 'Prédictions de pics');

    cy.contains('button', 'Déconnexion').click();

    cy.location('pathname').should('eq', '/login');
    cy.window().its('localStorage').invoke('getItem', TOKEN_KEY).should('be.null');
  });
});
