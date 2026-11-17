# Deployment

## Runtime and storage

`railway.toml` selects the Dockerfile builder and restart-on-failure policy. Docker
runs `python serve.py`: one Uvicorn worker serving Flask and native MCP through
`asgi.create_app()`. Repository configuration overrides Railway service settings.

Production runs in the `web` service. Check its source branch and deployment settings
in Railway before a release. Keep the persistent volume mounted at `/app/data`. SQLite lives at
`/app/data/app.db`; filesystem sessions live at `/app/data/flask_session`. Keep this
volume attached across deployments. `db.create_all()` creates missing tables only;
schema changes require migrations.

Private hostnames, project identifiers, and CLI authentication instructions belong
in gitignored `operations.local.md`. They do not belong in tracked documentation.

## Configuration

Dynaconf loads `settings.toml`, then `.secrets.toml`; `LANGTUT_*` overrides take
precedence. `RAILWAY_ENVIRONMENT=production` selects production settings. Both Flask
and MCP use the same resolved configuration and database path.
Local defaults use `data/app.db`, `flask_session/`, and loopback binding; production
uses the volume paths above and secure session cookies.

| Variable | Purpose |
|---|---|
| `LANGTUT_ALLOWED_HOSTS` | Required array of bare hostnames; include the deployment hostname and `healthcheck.railway.app` |
| `LANGTUT_MCP_ENABLED` | Defaults to `false`; `true` exposes the public MCP experiment |
| `LANGTUT_MCP_ALLOWED_ORIGINS` | Array of exact origins, including scheme; defaults to `[]` in production |
| `LANGTUT_MCP_REQUESTS_PER_MINUTE` | Process-wide MCP request limit, default 60 |
| `LANGTUT_DATABASE_PATH` | Overrides the shared SQLite path |
| `LANGTUT_BIND_HOST` | Defaults to `127.0.0.1` locally and `0.0.0.0` in production |
| `LANGTUT_PORT` | Overrides Railway's `PORT`; normally leave unset |
| `LANGTUT_PROXY_TRUSTED_IPS` | Trusted proxy IP/CIDR array; defaults to none; configure only verified peers |
| `LANGTUT_CLIENT_SECRETS_JSON` | Google OAuth client credentials |
| `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` | TTS/GCS service-account credentials |
| `LANGTUT_ENCRYPTION_KEY` | Stable Fernet key needed to decrypt stored refresh tokens |
| `LANGTUT_SECRET_KEY` | Stable Flask session signing secret |
| `LANGTUT_VERBS_IMPORT_API_KEY` | Optional key for authenticated verb imports |

Allowed hosts validate the destination hostname. MCP origins validate an `Origin`
header **when present**: an empty list accepts requests without that header and
rejects requests with it. Origins are not user authentication or browser CORS.
The same-origin Flask UI needs no CORS configuration. MCP requests from servers do
not require browser CORS permissions.

The launcher binds to `0.0.0.0` in production and honors `PORT`. It trusts forwarded
headers only from configured proxies. Production Google OAuth explicitly generates
HTTPS callbacks. Preserve that behavior when changing proxy handling.

## Healthcheck and verification

Railway probes `/` with a 300-second startup timeout. The anonymous homepage returns
the login page. This checks website startup, not Google APIs, authenticated flows,
or MCP tool execution. The probe uses `Host: healthcheck.railway.app`.

The check runs during deployment, not continuously. A service with an attached
volume can have brief redeployment downtime. See Railway's
[healthchecks](https://docs.railway.com/deployments/healthchecks) and
[configuration precedence](https://docs.railway.com/config-as-code/reference).

For a release, run the repository checks in [AGENTS.md](../AGENTS.md), verify Google
login and study/audio behavior, and use the [MCP smoke client](mcp.md). Verify backups
and rehearse restoration before schema or data migrations.

## Auth cutover

Existing LangTut databases require an explicit migration before the new application
starts. A new database uses the current schema at initialization.

1. Stop the old app and take a consistent SQLite backup. Verify restoration on a copy.
2. With the app stopped, run the migration against the intended SQLite file.

   ```bash
   uv run python -m scripts.migrate_auth --database /path/to/app.sqlite
   ```

3. Run the command again to check that it copies zero rows. Start the new app and
   verify sign-in, Sheets access, and the verbs screen.

The migration copies the encrypted value and timestamps from the latest legacy grant
per user. The largest record ID breaks ties. The migration leaves legacy rows in place
and records that it ran, so rerunning it will leave rotated and disconnected grants
alone. Migrated scopes start unknown. The migration makes no Google requests.

Existing browsers must sign in again once. New sign-ins expire after seven days
without extension. **Log out** ends the current browser session. **Log out everywhere**
invalidates all of that user's browser sessions. **Disconnect Google Sheets** removes
the local grant and cached access for all browsers and preserves LangTut login and
linked spreadsheet records.

To revoke the provider grant, remove LangTut from [Google Account connections](https://myaccount.google.com/connections).
Google revocation can invalidate all OAuth scopes and tokens granted to the project.
Local disconnect leaves previously issued Google tokens valid until Google expires or
revokes them. With the combined consent flow, signing in again may only restore offline
access after the old provider grant has been removed. [Google OAuth revocation documentation](https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke)

### Rollback

Stop the app and keep a backup of the current database before rolling back. The prior
app can read the migrated schema and uses the legacy grant rows. Before starting it,
use an empty browser session directory and review accounts that disconnected or lost
Google authorization during the cutover. Their legacy grants must be reconciled to
avoid restoring access. Users whose refresh tokens rotated may need to reconnect.
Restoring the pre-cutover backup also restores its prior grants and discards subsequent
SQLite writes. Review that tradeoff before restoring it.

## CLI variable changes

Authenticate using `operations.local.md` and confirm the target with `railway status`.
Replace the hostname placeholder; omit scheme, port, and path:

```bash
railway variable set --service web --environment production --skip-deploys \
  'LANGTUT_ALLOWED_HOSTS=["YOUR_DEPLOYMENT_HOSTNAME","healthcheck.railway.app"]' \
  'LANGTUT_MCP_ENABLED=true'
```

`--skip-deploys` saves configuration without triggering deployment. Changes take
effect when the service is next deployed. To disable MCP and trigger deployment:

```bash
railway variable set --service web --environment production \
  'LANGTUT_MCP_ENABLED=false'
```

Disabled MCP returns 404 while the website remains available. Agents require owner
confirmation immediately before production mutations; see [AGENTS.md](../AGENTS.md).
