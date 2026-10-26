describe('Tableau de bord', () => {
  it("affiche l'utilisateur et les trois blocs de données", () => {
    cy.intercept('GET', '/api/predictions').as('predictions');
    cy.intercept('GET', '/api/history*').as('history');
    cy.intercept('GET', '/api/recommendations').as('recommendations');

    cy.loginAsNewUser('/').then((email) => {
      cy.contains('header', 'EnerVision');
      cy.contains('header', email);
      cy.contains('header', 'user');
    });

    // La page demande 24 h d'historique
    cy.wait('@history').its('request.url').should('include', 'days=1');
    cy.wait(['@predictions', '@recommendations']);

    cy.contains('Chargement…').should('not.exist');
    cy.contains('section', 'Prédictions de pics').find('tbody tr').should('have.length.greaterThan', 0);
    cy.contains('section', 'Recommandations').find('li').should('have.length.greaterThan', 0);
    cy.contains('section', 'Historique (24 h)').find('tbody tr').should('have.length.greaterThan', 0);
  });

  it("affiche les valeurs renvoyées par l'API", () => {
    // Réponses fixées : le test ne dépend pas des données d'exemple de l'API
    cy.intercept('GET', '/api/predictions', [
      { timestamp: '2026-10-26T18:00:00Z', predicted_kw: 4.26, confidence: 0.9 },
    ]);
    cy.intercept('GET', '/api/history*', [
      { timestamp: '2026-10-26T08:00:00Z', consumption_kw: 2.5 },
      { timestamp: '2026-10-26T09:00:00Z', consumption_kw: 3.1 },
    ]);
    cy.intercept('GET', '/api/recommendations', [
      {
        id: 1,
        title: 'Décaler la filtration',
        message: 'Lancez la filtration avant 17h.',
        estimated_saving_kw: 1.8,
      },
    ]);

    cy.loginAsNewUser('/');

    cy.contains('section', 'Prédictions de pics').within(() => {
      cy.get('tbody tr').should('have.length', 1);
      cy.contains('4.3 kW');
      cy.contains('90%');
    });
    cy.contains('section', 'Recommandations').within(() => {
      cy.contains('Décaler la filtration');
      cy.contains('Lancez la filtration avant 17h.');
      cy.contains('Économie estimée : 1.8 kW');
    });
    cy.contains('section', 'Historique (24 h)').find('tbody tr').should('have.length', 2);
  });

  it("affiche un message d'erreur si une route de données échoue", () => {
    cy.intercept('GET', '/api/predictions', { statusCode: 500, body: {} });

    cy.loginAsNewUser('/');

    cy.contains("Impossible de charger les données depuis l'API.");
    cy.contains('h2', 'Prédictions de pics').should('not.exist');
    // Une erreur 500 ne déconnecte pas : seule une 401 le fait
    cy.location('pathname').should('eq', '/');
  });
});
