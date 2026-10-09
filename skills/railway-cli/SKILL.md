---
name: railway-cli
description: Inspect LangTut on Railway with the CLI, including production status, logs, metrics, workspace billing, and browser reauthentication. Use for Railway operational requests in this repo.
---

# Railway CLI

Run the installed `railway` executable from the repository root. Start with
`railway --version` and `railway --help`; use `railway <command> --help` for current flags.
Follow the credential and production-access rules in [AGENTS.md](../../AGENTS.md).

## Authentication

For project-scoped production inspection, source the existing credential file only in
the same non-traced shell invocation as the command:

```bash
set +x
source "$HOME/.config/langtut/railway.env"
railway status
```

Never inspect or expose that file or token. On authentication failure, report the failure
without credential diagnostics; ask the user to replace the configured token when needed.

For workspace billing or account access, use the saved browser login without sourcing
the production token. Project tokens can lack permission for these operations.
To sign in again, run:

```bash
unset RAILWAY_TOKEN RAILWAY_API_TOKEN
railway login
```

Let the user finish sign-in and CLI authorization in the browser, then verify with
`railway whoami`. Keep token variables unset in each subsequent account-level invocation.
Use `railway login --browserless` only when a local browser is unavailable.
Browser login creates a separate CLI session; it does not refresh or replace the
project token in the credential file. An Unauthorized billing response alone does not
prove that project token expired.

## Useful read-only commands

```bash
railway status                       # Linked project, environment, and service
railway logs --help                  # Choose bounded logs and relevant filters
railway metrics --help               # Resource and HTTP metric options
railway usage --json                 # Workspace billing period, usage, and estimates
railway usage --period previous --json
railway usage projects --json        # Usage by project
railway usage limit status           # Inspect configured limits
```

For billing, the CLI defaults to the workspace owning the linked project. Use
`--workspace <name-or-id>` to select another workspace. Report usage separately from
the subscription fee; do not infer the plan tier from usage totals.

To inspect the actual plan, discover the live API schema before querying:

```bash
railway api describe Query.workspace
railway api describe Workspace
railway api describe Plan
railway api 'query($id: String!) { workspace(workspaceId: $id) { name plan } }' --raw-var id=<workspace-id>
```

Take the workspace ID from the usage response rather than hardcoding a personal ID.
`railway api` also accepts mutations: use only queries for inspection.

Require explicit user confirmation immediately before any production mutation,
including `up`, `redeploy`, `restart`, variable/service/environment changes, or changes
to usage limits. Do not retrieve variable values without an explicit request.

References: [CLI login](https://docs.railway.com/cli/login),
[usage](https://docs.railway.com/cli/usage), [API](https://docs.railway.com/cli/api).
