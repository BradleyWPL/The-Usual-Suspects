<!--
File: docs/security.md
History: Version 0.3, October 17, 2026
Program: Record the security controls that apply to the local synthetic-data demo and its public-deployment boundary.
Input: API routes, browser rendering, environment configuration, Compose services, and project data flows.
Processing: Document implemented protections, out-of-scope controls, and checks required before any public deployment.
Output: A security posture checklist that prevents the local prototype from being mistaken for a production service.
-->
# Security posture

## Current local demo

The app is for generated synthetic records and binds to loopback in both `run.ps1` and Docker Compose. It has no real users, signup, login, session cookies, password reset, file upload, payment processing, external AI API, or administrative route. Those features are not implemented because they have no corresponding product flow. Do not load private company or employee records into this demo.

- The checked Git history was scanned for common API-key, private-key, and credential-assignment patterns. Scan findings should be recorded without copying secret values into reports. A clean pattern scan is not proof that every possible secret format has been detected.
- `.env` and local databases, datasets, logs, experiment output, backups, and build output are excluded from Git. Compose requires separate administrator and application passwords from `.env`; there is no committed database password.
- The setup container provisions `incidentlens_app`. The API container receives only that restricted connection string. The runtime role can read proposal/review state, update proposal status, and insert/update review notes; it cannot create tables, administer PostgreSQL, or read the isolated truth-label table.
- This is plain PostgreSQL, not Supabase: there is no browser-visible anonymous/master database key and no RLS policy layer. Browser code calls the same-origin API; the database accepts only container-side connections with the restricted role.
- The database is not published on a host port. The web app port is bound to `127.0.0.1`.
- Reviewer notes are limited to 2,000 characters, trimmed, and stored through parameterized SQL statements. Statuses, cluster IDs, search length, and pagination have server-side bounds.
- Dynamic UI text is HTML-escaped before being assigned to HTML templates. Lit escapes interpolated component text. No upload surface exists.
- API responses are marked `no-store`; the API adds a restrictive Content Security Policy, `nosniff`, frame denial, referrer policy, permissions policy, and same-origin resource policy. HSTS is sent only if the request reaches the app over HTTPS.
- The browser sends no credentials/cookies and the API does not enable cross-origin requests. CSRF protection is therefore not needed for the current same-origin local workflow. There are no login endpoints to rate-limit or protect from bots.
- No external service API keys or usage-billed calls are configured, so spend caps and billing alerts do not apply. Google Fonts is the only third-party browser request in the dashboard.
- A backup command is provided for the local PostgreSQL review state. Schedule it and keep an off-device copy if that state matters.

## Required before public production use

This project is not ready to expose to the public internet. Before deployment, choose and configure an owned domain and hosting provider, then add an authentication provider, server-side user/role authorization, abuse controls, and a TLS reverse proxy that redirects HTTP to HTTPS. Configure secure session cookies only if sessions are introduced, CSRF protection for cookie-authenticated writes, login/signup rate limits and bot defense if accounts are added, production database backup/restore testing, monitoring and billing alerts for any paid integrations, and deployment-specific security headers. Add private-data retention and encryption policies only after a real-data hosting design is approved.

Set `PUBLIC_SITE_URL` to the actual HTTPS origin/base URL in the deployment environment to enable the canonical URL, `robots.txt` policy, social preview image, and sitemap. Until then, the local crawler policy disallows indexing and `/sitemap.xml` returns not found. DNS, domain registration, public hosting, TLS certificates, account creation, and spend controls cannot be configured from this repository alone.

Run `npm audit` and `pip-audit -r requirements.lock.txt` from a network-enabled environment before release. Registry audit calls could not reach npm/PyPI from the current restricted environment, so this session cannot certify dependency vulnerability status.
