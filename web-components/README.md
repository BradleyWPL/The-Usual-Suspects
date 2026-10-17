<!--
File: web-components/README.md
History: Version 0.2, October 17, 2026
Program: Explain how to build and view the reusable IncidentLens Lit components.
Input: npm and the component source in src/ and demos/.
Processing: Install the locked dependencies, generate the element manifest, build, or start Vite.
Output: Plain HTML and React component demos with a checked-in Custom Elements Manifest.
-->
# IncidentLens Web Components

This package belongs to **The Usual Suspects** project. It provides six Lit custom elements:

- `lens-cluster-card` — cluster summary and review status.
- `lens-evidence-list` — ranked root-cause evidence and heuristic scores.
- `lens-noise-meter` — clustered share of the input records.
- `lens-incident-timeline` — incident counts with an optional change marker.
- `lens-dependency-graph` — affected configuration items and dependency edges.
- `lens-proposal-form` — local proposal event with a reviewer note.

Run these commands from this directory:

```powershell
npm ci
npm run manifest
npm run build
npm run dev
```

The development server displays the plain HTML and React examples. Proposal events in these component examples are local demonstration events; the main `web/` application uses the FastAPI review endpoint.
