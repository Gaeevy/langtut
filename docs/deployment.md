# Deployment

The repository defines the intended runtime. Verify the deployed source branch,
configuration, volume, and backup before a release. Private targets and CLI context
live in gitignored `operations.local.md`. Production mutations require the approval
specified in [AGENTS.md](../AGENTS.md#shared-cli-skills-and-local-operations).

## Runtime and configuration

`railway.toml` selects the Dockerfile and restart-on-failure policy. The image starts
`serve.py` with one Uvicorn worker serving Flask and native MCP. Keep the persistent
volume at `/app/data`; SQLite uses `/app/data/app.db` and filesystem sessions use
`/app/data/flask_session`. Configuration in the repository takes precedence over
corresponding dashboard settings. [Railway configuration reference](https://docs.railway.com/config-as-code/reference)

`app/config.py` loads `settings.toml` and gitignored `.secrets.toml` through Dynaconf,
then validates resolved settings with Pydantic. `LANGTUT_*` variables take precedence.
`RAILWAY_ENVIRONMENT=production` selects production defaults.
[README](../README.md#local-setup) owns local setup.

| Variable | Runtime purpose |
|---|---|
| `LANGTUT_ALLOWED_HOSTS` | Bare deployment hostnames, including `healthcheck.railway.app` |
| `LANGTUT_DATABASE_PATH` | Shared SQLite path |
| `LANGTUT_SECRET_KEY` | Stable Flask session signing key |
| `LANGTUT_ENCRYPTION_KEY` | Stable Fernet key for stored Google refresh tokens |
| `LANGTUT_CLIENT_SECRETS_JSON` | Google OAuth web client configuration |
| `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` | TTS/GCS service-account configuration |
| `LANGTUT_VERBS_IMPORT_API_KEY` | Optional `X-Import-Key` for verb imports |
| `LANGTUT_GOOGLE_IDENTITY_SCOPES`, `LANGTUT_GOOGLE_SHEETS_SCOPES` | Override the scope lists in `settings.toml` |
| `LANGTUT_MCP_ENABLED` | Enable the public demo; default `false` |
| `LANGTUT_MCP_ALLOWED_ORIGINS` | Accepted MCP origins; production default is empty |
| `LANGTUT_MCP_REQUESTS_PER_MINUTE` | Per-process limit; default 60 |
| `LANGTUT_BIND_HOST`, `LANGTUT_PORT` | Bind address and port; production defaults to `0.0.0.0` and Railway's `PORT` |
| `LANGTUT_PROXY_TRUSTED_IPS` | Verified proxy IPs/CIDRs; default empty |

Production uses secure session cookies and HTTPS OAuth callbacks. Forwarded headers
are trusted only from configured proxies. The combined app requires allowed hosts
and OAuth client configuration at startup. MCP origin behavior is defined in
[mcp.md](mcp.md#tool-contract).

## Healthcheck and release verification

Railway probes `/` with a 300-second startup timeout, using
`Host: healthcheck.railway.app`. The anonymous login page exercises startup. Run
separate checks for authenticated flows and external services. Railway healthchecks
run during deployment; they stop after the deployment goes live. A volume-backed
service can have deployment downtime. [Railway healthchecks](https://docs.railway.com/deployments/healthchecks),
[volumes](https://docs.railway.com/volumes)

Before release, run the [repository checks](../AGENTS.md#commands), the auth checklist
below, [MCP smoke tests](mcp.md#local-testing), and [device audio checks](audio.md#manual-verification-checklist).
Use synthetic data for automated verification. Verify SQLite-consistent backups and
rehearse restoration before schema changes. Migration procedures that touch the volume
must run after it is mounted; Railway volumes are unavailable during build and
pre-deploy. [Railway volumes](https://docs.railway.com/volumes)

## Auth cutover

Existing databases need `scripts.migrate_auth` before this version starts. A new
installation creates the current schema. Remove obsolete `LANGTUT_SCOPES` overrides
when preparing the release; the new scope keys are listed above.

1. Stop the old app. Take a consistent SQLite backup and verify restoration on a copy.
2. Run against the intended existing file while the app remains stopped.

   ```bash
   uv run python -m scripts.migrate_auth --database /path/to/app.sqlite
   ```

3. Rerun the command and check that it copies zero rows. Start the new app and verify
   the flows below. Existing browser sessions must sign in again once.

The migration selects each user's latest legacy grant by `last_used`, then ID. It
copies encrypted values and timestamps, records completion, and preserves legacy rows.
Scopes start unknown. Reruns preserve rotated or disconnected connections. Migration
performs SQLite work only. [Architecture](architecture.md#identity-sessions-and-sheets-access)
owns the resulting session and connection lifecycle.

### Rollback

Stop the app and back up the current database first. The previous version can read
legacy rows in the migrated schema. Use an empty browser session directory and
reconcile grants for users who disconnected or lost authorization during cutover.
Otherwise rollback can restore access they removed. Token rotation can require
reconnection. Restoring the pre-cutover database also discards subsequent SQLite
writes. Define the rollback window and reconcile those writes before restoration.

### Sign-in and Sheets consent verification

Run with the owner's local Google configuration. Both authorization purposes use
`/oauth2callback`. Automated mocks cover failure cases; these checks confirm provider
and browser behavior.

1. Sign in in a fresh browser. Verify identity scopes and access to irregular verbs.
   Vocabulary screens should offer **Connect Google Sheets**.
2. Connect with the same Google account and grant Sheets access. Verify setup or the
   vocabulary screen, then **Reconnect Google Sheets** and verify offline access.
3. Deny consent, grant partial consent, and choose a different account on separate
   attempts. Verify login and any existing connection survive these failures.
4. Start login and connect in separate tabs; complete each. Verify that a repeated
   callback fails. Leave another attempt open ten minutes and verify it expires.
5. Disconnect, verify verbs remain usable, then connect again. Check current-device
   and all-device logout against the [lifecycle table](architecture.md#identity-sessions-and-sheets-access).
6. Study using form and AJAX submissions, complete and end review early, and listen.
   Apply the [physical-device checklist](audio.md#manual-verification-checklist).
7. Revoke a Sheets grant before saving study results. Reconnect, choose Resume on the
   homepage, and verify the retained work saves. For a failed review choice, verify
   the current card is shown again and the explicit resubmission saves it once.

Local disconnect removes LangTut's grant and cache. To revoke issued tokens at
Google, remove LangTut from [Google Account connections](https://myaccount.google.com/connections).
Google revocation can invalidate all scopes and tokens granted to the OAuth project.
[Google revocation documentation](https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke)

## CLI variable changes

Authenticate and verify the intended target using `operations.local.md`. Substitute
the deployment hostname without a scheme or path.

```bash
railway variable set --service web --environment production --skip-deploys \
  'LANGTUT_ALLOWED_HOSTS=["YOUR_DEPLOYMENT_HOSTNAME","healthcheck.railway.app"]' \
  'LANGTUT_MCP_ENABLED=true'
```

`--skip-deploys` applies the variables on the next deployment. To disable MCP and
trigger deployment, set `LANGTUT_MCP_ENABLED=false` without that flag. Use the
[MCP guide](mcp.md) to verify enabled and disabled behavior.
