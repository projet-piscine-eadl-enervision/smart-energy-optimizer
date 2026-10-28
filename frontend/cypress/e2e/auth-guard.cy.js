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
    // Profil réel : un compte neuf sans site arrive sur l'accueil, qui lui affiche le message
    cy.loginAsNewUser('/login', null);

    cy.location('pathname').should('eq', '/');
    cy.contains('main', 'Aucun site');
  });

  it("déconnecte quand le jeton est refusé par l'API", () => {
    // Le garde ne voit qu'un jeton présent ; c'est l'API qui le refuse (401),
    // puis l'intercepteur supprime le jeton et renvoie vers /login
    cy.visitAsLoggedIn('/', 'jeton-invalide');

    cy.location('pathname').should('eq', '/login');
    cy.window().its('localStorage').invoke('getItem', TOKEN_KEY).should('be.null');
  });

  it("n'appelle pas les routes protégées sans jeton", () => {
    cy.request({ url: '/api/auth/me', failOnStatusCode: false }).its('status').should('eq', 401);
  });
});
