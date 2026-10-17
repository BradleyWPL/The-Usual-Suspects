// File: web-components/vite.config.ts
// History: Version 0.2, October 17, 2026
// Program: Configure Vite dev and production builds for the component examples.
// Input: Vite build invocation and the React demo source.
// Processing: Set the React plugin and plain/React page entry points.
// Output: Local demo server and built example bundles.

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    // Keep production outputs minified and do not publish source maps from the component demo.
    sourcemap: false,
    rollupOptions: {
      input: {
        plain: resolve(here, 'demos/plain/index.html'),
        react: resolve(here, 'demos/react/index.html'),
      },
    },
  },
});
