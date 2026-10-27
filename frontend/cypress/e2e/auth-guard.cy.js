import { TOKEN_KEY } from '../support/helpers';

describe('Accès protégé par le garde', () => {
  it('renvoie un visiteur non connecté vers /login', () => {
    cy.visit('/');

    cy.location('pathname').should('eq', '/login');
    cy.contains('h1', 'Connexion');
  });

  it('renvoie une adresse inconnue vers /login pour un visiteur non connecté', () => {
    cy.visit('/page-qui-n-existe-pas');

    cy.location('pathname').should('eq', '/login');
  });

  it('renvoie un utilisateur connecté de /login vers le tableau de bord', () => {
    cy.loginAsNewUser('/login');

    cy.location('pathname').should('eq', '/');
    cy.contains('h2', 'Prédictions de la consommation');
  });

  it('déconnecte quand le jeton est refusé par l\'API', () => {
    // Le garde ne voit qu'un jeton présent ; c'est l'API qui le refuse (401),
    // puis l'intercepteur supprime le jeton et renvoie vers /login
    cy.visitAsLoggedIn('/', 'jeton-invalide');

    cy.location('pathname').should('eq', '/login');
    cy.window().its('localStorage').invoke('getItem', TOKEN_KEY).should('be.null');
  });

  it("n'appelle pas les routes protégées sans jeton", () => {
    cy.request({ url: '/api/auth/me', failOnStatusCode: false })
      .its('status')
      .should('eq', 401);
  });
});
