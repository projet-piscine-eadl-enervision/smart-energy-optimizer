import { DEFAULT_PASSWORD, uniqueEmail } from '../support/helpers';

describe('Inscription', () => {
  beforeEach(() => {
    cy.visit('/login');
    cy.contains('button', 'Pas de compte ? Inscris-toi').click();
  });

  it("passe le formulaire en mode inscription et peut revenir à la connexion", () => {
    cy.contains('h1', 'Créer un compte');
    cy.contains('button[type="submit"]', "S'inscrire");
    cy.get('input[formcontrolname="password"]').should('have.attr', 'autocomplete', 'new-password');

    cy.contains('button', 'Déjà un compte ? Connecte-toi').click();
    cy.contains('h1', 'Connexion');
  });

  it('crée un compte, connecte directement et ouvre le tableau de bord', () => {
    const email = uniqueEmail();
    cy.intercept('POST', '/api/auth/register').as('registerRequest');
    cy.intercept('POST', '/api/auth/login').as('loginRequest');

    cy.submitAuthForm(email, DEFAULT_PASSWORD);

    cy.wait('@registerRequest').its('response.statusCode').should('eq', 201);
    cy.wait('@loginRequest').its('response.statusCode').should('eq', 200);
    cy.location('pathname').should('eq', '/');
    cy.contains('header', email);
    cy.contains('header', 'user');
    // Un compte neuf n'a pas de site : c'est un admin qui le lui attribue
    cy.contains('main', 'Aucun site');
  });

  it('refuse un email déjà utilisé', () => {
    const email = uniqueEmail();
    cy.createUser(email);

    cy.submitAuthForm(email, DEFAULT_PASSWORD);

    cy.contains('Cet email est déjà utilisé.');
    cy.location('pathname').should('eq', '/login');
  });

  it("vérifie le mot de passe avant d'appeler l'API", () => {
    cy.intercept('POST', '/api/auth/register').as('registerRequest');

    cy.submitAuthForm(uniqueEmail(), 'court');

    cy.contains('8 caractères minimum.');
    cy.get('@registerRequest.all').should('have.length', 0);
  });
});
