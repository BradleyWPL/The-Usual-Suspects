// File: web-components/custom-elements-manifest.config.mjs
// History: Version 0.2, October 17, 2026
// Program: Configure which source files feed the Lit custom-elements analyzer.
// Input: TypeScript component declarations under src/.
// Processing: Include component modules and skip dependency/build directories.
// Output: Analyzer settings used when producing custom-elements.json.

export default {
  globs: ['src/**/*.ts'],
  exclude: ['node_modules/**', 'dist/**'],
  outdir: '.',
  litelement: true,
};
