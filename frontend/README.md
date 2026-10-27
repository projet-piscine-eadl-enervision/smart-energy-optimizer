# Enervision

This project was generated using [Angular CLI](https://github.com/angular/angular-cli) version 22.2.3.

## Pages

| Adresse | Page |
|---|---|
| `/login` | connexion et inscription |
| `/` | tableau de bord : prévisions (pics en rouge), historique, recommandations, par site ou pour le total |
| `/peaks` | pics prévus : heure, site, seuil, dépassement |
| `/alerts` | alertes, actives ou résolues ; le badge de l'en-tête compte les actives (sondage toutes les 30 s) |
| `/sites`, `/sites/:id` | sites avec leur dernière mesure ; consommation par heure, jour, semaine ou mois et qualité des relevés |

Les pages vivent dans `src/app/pages/`, les services d'API dans `src/app/core/` et les éléments partagés (en-tête, sélecteur de site) dans `src/app/shared/`. Les tests des écrans passent par les vrais services : seul le réseau est simulé (`src/app/testing/api.ts`).

## Development server

To start a local development server, run:

```bash
ng serve
```

Once the server is running, open your browser and navigate to `http://localhost:4000/`. The application will automatically reload whenever you modify any of the source files.

## Code scaffolding

Angular CLI includes powerful code scaffolding tools. To generate a new component, run:

```bash
ng generate component component-name
```

For a complete list of available schematics (such as `components`, `directives`, or `pipes`), run:

```bash
ng generate --help
```

## Building

To build the project run:

```bash
ng build
```

This will compile your project and store the build artifacts in the `dist/` directory. By default, the production build optimizes your application for performance and speed.

## Running unit tests

To execute unit tests with the [Vitest](https://vitest.dev/) test runner, use the following command:

```bash
ng test
```

## Tests de bout en bout

Chaque test crée son propre compte (email unique), la base n'a pas besoin d'être vidée. En cas
d'échec, une capture d'écran est écrite dans `cypress/screenshots/` (ignoré par Git). Pour un
seul fichier : `docker compose --profile e2e run --rm e2e --browser chrome --spec e2e/login.cy.js`.

Scénarios Cypress dans `cypress/e2e/` : connexion, inscription, accès protégé par le garde,
tableau de bord, navigation, sites, alertes et pics prévus. Ils tournent contre la vraie pile (frontend, API, base), dans le conteneur
`e2e` (image `cypress/included`), donc sans Node ni Cypress installés dans WSL, et dans le job `e2e`
de la CI. Depuis la racine du dépôt :

```bash
docker compose up -d
docker compose --profile e2e run --rm e2e
```

## Additional Resources

For more information on using the Angular CLI, including detailed command references, visit the [Angular CLI Overview and Command Reference](https://angular.dev/tools/cli) page.
