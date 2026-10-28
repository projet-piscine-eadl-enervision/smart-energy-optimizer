describe('Tableau de bord', () => {
  const expectChartRendered = (sectionTitle) => {
    cy.contains('section', sectionTitle)
      .find('canvas')
      .should('have.length', 1)
      .and(($c) => {
        const el = $c[0];
        expect(el.width, 'largeur du canvas').to.be.greaterThan(0);
        expect(el.height, 'hauteur du canvas').to.be.greaterThan(0);
      });
  };

  it("montre à un compte neuf, sans site, qu'il doit en demander un, sans lire de données", () => {
    // Profil réel de l'API : un compte créé par l'inscription est un user sans site
    cy.intercept('GET', '/api/predictions*').as('predictions');
    cy.intercept('GET', '/api/history*').as('history');
    cy.intercept('GET', '/api/recommendations*').as('recommendations');

    cy.loginAsNewUser('/', null).then((email) => {
      cy.contains('header', 'Smart Energy Optimizer');
      cy.contains('header', email);
      cy.contains('header', 'user');
    });

    cy.contains('main', "Aucun site n'est encore rattaché à votre compte");
    cy.contains('h2', 'Prédictions de la consommation').should('not.exist');
    cy.get('@predictions.all').should('have.length', 0);
    cy.get('@history.all').should('have.length', 0);
    cy.get('@recommendations.all').should('have.length', 0);
  });

  it('affiche les trois blocs de données dans leur état vide', () => {
    cy.intercept('GET', '/api/predictions*', []).as('predictions');
    cy.intercept('GET', '/api/history*', []).as('history');
    cy.intercept('GET', '/api/recommendations*', []).as('recommendations');

    cy.loginAsNewUser('/');

    // La page demande 24 h d'historique
    cy.wait('@history').its('request.url').should('include', 'days=1');
    cy.wait(['@predictions', '@recommendations']);

    cy.contains('Chargement…').should('not.exist');
    cy.contains('section', 'Prédictions de la consommation').contains(
      'Aucune prévision disponible',
    );
    cy.contains('section', 'Historique (24 h)').contains('Aucune mesure sur cette période.');
    cy.contains('section', 'Recommandations').contains('Aucune recommandation pour le moment.');
  });

  it("affiche les recommandations renvoyées par l'API et alimente les graphiques", () => {
    cy.intercept('GET', '/api/predictions*', [
      {
        timestamp: '2026-10-26T18:00:00Z',
        site_id: 'ALL',
        predicted_kw: 4.26,
        is_peak: null,
        model_version: '1',
      },
    ]);
    cy.intercept('GET', '/api/history*', [
      { timestamp: '2026-10-26T08:00:00Z', consumption_kw: 2.5 },
      { timestamp: '2026-10-26T09:00:00Z', consumption_kw: 3.1 },
    ]);
    cy.intercept('GET', '/api/recommendations*', [
      {
        id: 1,
        title: 'Décaler la filtration',
        message: 'Lancez la filtration avant 17h.',
        estimated_saving_kw: 1.8,
        site_id: 'SITE001',
        target_time: '2026-10-26T18:00:00Z',
        alert_type: 'threshold',
      },
    ]);

    cy.loginAsNewUser('/');

    expectChartRendered('Prédictions de la consommation');
    expectChartRendered('Historique (24 h)');
    cy.contains('section', 'Recommandations').within(() => {
      cy.get('li').should('have.length', 1);
      cy.contains('Décaler la filtration');
      cy.contains('Lancez la filtration avant 17h.');
      cy.contains('Économie estimée : 1.8 kW');
    });
  });

  it("affiche un message d'erreur si une route de données échoue", () => {
    cy.intercept('GET', '/api/predictions*', { statusCode: 500, body: {} });
    cy.intercept('GET', '/api/history*', []);
    cy.intercept('GET', '/api/recommendations*', []);

    cy.loginAsNewUser('/');

    cy.contains("Impossible de charger les données depuis l'API.");
    // En erreur, le template n'affiche plus aucune section
    cy.contains('h2', 'Prédictions de la consommation').should('not.exist');
    cy.contains('h2', 'Historique (24 h)').should('not.exist');
    cy.contains('h2', 'Recommandations').should('not.exist');
    // Une erreur 500 ne déconnecte pas : seule une 401 le fait
    cy.location('pathname').should('eq', '/');
  });
});
