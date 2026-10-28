// @ts-check
// Lint du frontend : `npm run lint` (ng lint). La CI lance la même commande dans le job frontend.
// La mise en forme est laissée à Prettier (`npm run format:check`) : eslint-config-prettier, placé
// en dernier, coupe les règles de style qui le contrediraient.
const eslint = require('@eslint/js');
const { defineConfig } = require('eslint/config');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');
const prettier = require('eslint-config-prettier/flat');

// Organisation de src/app (voir README) : pages -> shared -> core, jamais dans l'autre sens.
// - core (services d'API, modèles) ne dépend d'aucun écran ;
// - shared (en-tête, sélecteur de site) sert plusieurs pages et n'en importe aucune ;
// - une page n'importe pas une autre page : ce qui est commun va dans shared ou core.
// - testing (simulation du réseau) n'est importé que par les tests.
const noPagesImport = {
  regex: '(^|/)pages(/|$)',
  message:
    'core et shared ne dépendent pas des pages : déplacer le code commun dans shared ou core.',
};
const noSharedImport = {
  regex: '(^|/)shared(/|$)',
  message: 'core ne dépend pas de shared : un service ou un modèle va dans core.',
};
const noTestingImport = {
  regex: '(^|/)testing(/|$)',
  message: 'src/app/testing est réservé aux tests (*.spec.ts).',
};

module.exports = defineConfig([
  {
    ignores: ['dist/', 'coverage/', '.angular/', 'cypress/'],
  },
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      tseslint.configs.recommended,
      tseslint.configs.stylistic,
      angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/directive-selector': [
        'error',
        { type: 'attribute', prefix: 'app', style: 'camelCase' },
      ],
      '@angular-eslint/component-selector': [
        'error',
        { type: 'element', prefix: 'app', style: 'kebab-case' },
      ],
    },
  },
  {
    files: ['src/app/core/**/*.ts'],
    ignores: ['**/*.spec.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        { patterns: [noPagesImport, noSharedImport, noTestingImport] },
      ],
    },
  },
  {
    files: ['src/app/shared/**/*.ts'],
    ignores: ['**/*.spec.ts'],
    rules: {
      'no-restricted-imports': ['error', { patterns: [noPagesImport, noTestingImport] }],
    },
  },
  {
    files: ['src/app/pages/**/*.ts'],
    ignores: ['**/*.spec.ts'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              // Depuis pages/<page>/, « ../autre-page/... » ou « ../../pages/... » vise une autre page.
              regex: String.raw`^\.\./[^.]|(^|/)pages(/|$)`,
              message: "Une page n'importe pas une autre page : passer par shared ou core.",
            },
            noTestingImport,
          ],
        },
      ],
    },
  },
  {
    files: ['**/*.html'],
    extends: [angular.configs.templateRecommended, angular.configs.templateAccessibility],
  },
  prettier,
]);
