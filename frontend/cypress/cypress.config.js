// Configuration Cypress des tests de bout en bout.
// Cypress tourne dans le conteneur e2e (docker-compose.yml, profil e2e), qui partage le réseau
// du conteneur frontend : l'application et son proxy /api répondent donc sur localhost:4000.
// Le dossier cypress/ est la racine du projet Cypress : monté seul dans le conteneur, il reste
// accessible en écriture (captures d'écran) sans exposer le reste du frontend.
// Objet simple, sans defineConfig : le module cypress n'est pas installé dans le projet.
module.exports = {
  e2e: {
    baseUrl: process.env.CYPRESS_BASE_URL || 'http://localhost:4000',
    specPattern: 'e2e/**/*.cy.js',
    supportFile: 'support/e2e.js',
    fixturesFolder: false,
    screenshotsFolder: 'screenshots',
    videosFolder: 'videos',
    downloadsFolder: 'downloads',
    // Le serveur de dev Angular compile à la première requête : on lui laisse le temps
    pageLoadTimeout: 120000,
    defaultCommandTimeout: 10000,
    video: false,
    screenshotOnRunFailure: true,
    viewportWidth: 1280,
    viewportHeight: 800,
  },
};
