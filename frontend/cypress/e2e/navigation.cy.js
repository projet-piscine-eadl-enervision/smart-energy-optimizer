describe('Navigation et pages de données', () => {
  const SITE = {
    site_id: 'SITE001',
    site_name: 'Usine Lyon',
    site_type: 'factory',
    location: 'Lyon',
    capacity_kw: 1200,
    status: 'active',
    last_consumption_kw: 842.35,
    last_reading_age_minutes: 3.4,
    last_quality: 'good',
  };
  const ALERT = {
    alert_id: 'ALR-SITE001-1',
    timestamp: '2026-10-27T10:00:00Z',
    received_at: '2026-10-27T10:01:00Z',
    site_id: 'SITE001',
    site_name: 'Usine Lyon',
    severity: 'high',
    alert_type: 'threshold',
    alert_label: 'Dépassement du seuil',
    message: 'Seuil de consommation dépassé',
    value: 132.8,
    threshold: 117,
    origin: 'api',
    status: 'active',
  };

  const stubEmptyData = () => {
    cy.intercept('GET', '/api/predictions*', []);
    cy.intercept('GET', '/api/history*', []);
    cy.intercept('GET', '/api/recommendations*', []);
  };

  it("propose les pages de l'application et passe de l'une à l'autre", () => {
    stubEmptyData();
    cy.intercept('GET', '/api/sites', []);
    cy.intercept('GET', '/api/alerts*', []);
    cy.intercept('GET', '/api/predictions/peaks*', []);

    cy.loginAsNewUser('/');
    cy.get('nav a').then(($links) => {
      expect([...$links].map((a) => a.textContent.replace(/\s+/g, ' ').trim())).to.deep.equal([
        'Tableau de bord',
        'Sites',
        'Pics prévus',
        'Alertes',
      ]);
    });

    cy.contains('nav a', 'Sites').click();
    cy.location('pathname').should('eq', '/sites');
    cy.contains('h2', 'Sites');

    cy.contains('nav a', 'Pics prévus').click();
    cy.location('pathname').should('eq', '/peaks');
    cy.contains('Aucun pic prévu');

    cy.contains('nav a', 'Alertes').click();
    cy.location('pathname').should('eq', '/alerts');
    cy.contains('Aucune alerte.');

    cy.contains('nav a', 'Tableau de bord').click();
    cy.location('pathname').should('eq', '/');
  });

  it("liste les sites et ouvre le détail d'un site", () => {
    stubEmptyData();
    cy.intercept('GET', '/api/sites', [SITE]);
    cy.intercept('GET', '/api/sites/SITE001/consumption*', [
      { timestamp: '2026-10-25T22:00:00Z', energy_kwh: 1200.5, max_kw: 80 },
      { timestamp: '2026-10-26T22:00:00Z', energy_kwh: 1180, max_kw: 78 },
    ]).as('consumption');
    cy.intercept('GET', '/api/sites/SITE001/quality*', {
      site_id: 'SITE001',
      days: 7,
      readings: 1000,
      missing_ratio: 0.05,
      by_quality: { good: 900, partial: 60, degraded: 30, critical: 10 },
      sensor_outages: 3,
    });

    cy.loginAsNewUser('/sites');
    cy.contains('tbody tr', 'SITE001').within(() => {
      cy.contains('Usine Lyon');
      cy.contains('842.4');
      cy.contains('good');
      cy.contains('a', 'SITE001').click();
    });

    cy.location('pathname').should('eq', '/sites/SITE001');
    cy.wait('@consumption').its('request.url').should('include', 'period=day');
    cy.contains('section', 'Consommation').find('canvas').should('have.length', 1);
    cy.contains('section', 'Qualité des relevés').within(() => {
      cy.contains('1,000 relevés sur 7 jours');
      cy.contains('Pannes de capteur : 3');
    });

    cy.contains('button', 'Mois').click();
    cy.wait('@consumption').its('request.url').should('include', 'period=month');
  });

  it('affiche les alertes actives et leur nombre dans le badge', () => {
    stubEmptyData();
    cy.intercept('GET', '/api/sites', [SITE]);
    cy.intercept('GET', '/api/alerts*', [ALERT]).as('alerts');

    cy.loginAsNewUser('/');
    cy.wait('@alerts').its('request.url').should('include', 'status=active');
    cy.contains('nav a', 'Alertes').contains('1');

    cy.contains('nav a', 'Alertes').click();
    cy.contains('li', 'Dépassement du seuil').within(() => {
      cy.contains('SITE001 · Usine Lyon');
      cy.contains('Seuil de consommation dépassé');
      cy.contains('seuil 117.0');
    });
  });

  it("affiche les pics prévus avec leur seuil et leur dépassement", () => {
    stubEmptyData();
    cy.intercept('GET', '/api/sites', [SITE]);
    cy.intercept('GET', '/api/alerts*', []);
    cy.intercept('GET', '/api/predictions/peaks*', [
      {
        timestamp: '2026-10-27T19:00:00Z',
        site_id: 'SITE001',
        predicted_kw: 120.5,
        threshold_kw: 100,
        excess_kw: 20.5,
        model_version: '1',
      },
    ]).as('peaks');

    cy.loginAsNewUser('/peaks');
    cy.wait('@peaks').its('request.url').should('include', 'hours=24');
    cy.contains('tbody tr', 'SITE001').within(() => {
      cy.contains('120.5');
      cy.contains('100.0');
      cy.contains('20.5');
    });

    cy.contains('button', '72 h').click();
    cy.wait('@peaks').its('request.url').should('include', 'hours=72');
  });

  it("filtre le tableau de bord par site", () => {
    cy.intercept('GET', '/api/sites', [SITE]);
    cy.intercept('GET', '/api/alerts*', []);
    cy.intercept('GET', '/api/predictions*', []).as('predictions');
    cy.intercept('GET', '/api/history*', []).as('history');
    cy.intercept('GET', '/api/recommendations*', []).as('recommendations');

    cy.loginAsNewUser('/');
    cy.wait(['@predictions', '@history', '@recommendations']);

    cy.get('select').select('SITE001 · Usine Lyon');
    cy.wait('@predictions').its('request.url').should('include', 'site_id=SITE001');
    cy.wait('@history').its('request.url').should('include', 'site_id=SITE001');
    cy.wait('@recommendations').its('request.url').should('include', 'site_id=SITE001');
  });
});
