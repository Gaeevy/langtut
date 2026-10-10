# Deployment

LangTut runs Flask and the optional native MCP adapter in one Uvicorn process via
`serve.py` / `asgi.create_app()`. Docker runs `python serve.py` with one worker,
binding to Railway's `PORT`. Shared configuration comes from `settings.toml` and
`LANGTUT_*` overrides; `RAILWAY_ENVIRONMENT=production` selects production defaults.
MCP is a public, read-only spreadsheet-name lookup by email, disabled by default.

## Railway snapshot — 2026-10-10

Read-only inspection confirmed the production `web` service:

- Deploys from `master`, without waiting for CI checks; one running replica.
- Has a persistent volume at `/app/data`, matching SQLite `/app/data/app.db` and
  sessions `/app/data/flask_session`.
- Has no service-level build/start command or root-directory override, no fixed
  domain target port, and no sleeping. Restart policy is on failure (10 retries).
- Reports Nixpacks at service level, but repository `railway.toml` explicitly
  selects the Dockerfile builder. Config in code takes precedence.
- Has OAuth, service-account, encryption, session-secret, and verb-import variables.
  Only variable names were inspected; values were not retrieved.
- Does not yet have `LANGTUT_ALLOWED_HOSTS` or `LANGTUT_MCP_ENABLED` configured.
  No healthcheck was configured at inspection time.

Use this snapshot for planning; recheck live state before deployment or after
configuration changes. Private targets and CLI authentication are in gitignored
`operations.local.md`; do not copy their identifiers into tracked files.

## Next deployment

1. Set `LANGTUT_ALLOWED_HOSTS` to a TOML/JSON array containing the deployment
   hostname (no scheme/path) and `healthcheck.railway.app`. Startup requires a
   nonempty list. Set `LANGTUT_MCP_ENABLED=true` to enable the public experiment.
2. `railway.toml` now checks `/` with a 300-second timeout. An anonymous request
   renders the login page. This verifies website startup, not Google APIs or MCP;
   the probe hostname must be allowed. The check becomes active on deployment.
3. After deployment, verify Google login and run `scripts/mcp_smoke.py` against
   the HTTPS `/mcp` URL; see [MCP setup](mcp.md). Local browser, container, and
   enabled/disabled MCP checks passed before this release.

`LANGTUT_MCP_ENABLED=false` disables MCP on the next deployment/restart while the
website remains available. No CORS or proxy-trust override is required for the
current server-to-server experiment. Proxy topology remains unverified; leave
`LANGTUT_PROXY_TRUSTED_IPS` unset until verified. Production OAuth explicitly uses
HTTPS callbacks, which still need a real deployment check.

Railway healthchecks run at deployment time, not continuously. The attached volume
means redeployments can still have brief downtime. See Railway's
[healthcheck documentation](https://docs.railway.com/deployments/healthchecks) and
[configuration precedence](https://docs.railway.com/config-as-code/reference).

## Set variables with the CLI

Authenticate as described in `operations.local.md`, confirm `railway status`, and
replace `YOUR_DEPLOYMENT_HOSTNAME` below. This updates production configuration;
`--skip-deploys` saves the variables without immediately deploying the old code.

```bash
railway variable set --service web --environment production --skip-deploys \
  'LANGTUT_ALLOWED_HOSTS=["YOUR_DEPLOYMENT_HOSTNAME","healthcheck.railway.app"]' \
  'LANGTUT_MCP_ENABLED=true'
```

Set these before merging to `master`, which triggers deployment. Keep the existing
credential and encryption variables unchanged. Agents must obtain owner approval
immediately before production mutations.
