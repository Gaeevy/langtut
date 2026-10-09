---
name: gcp-cli
description: Use gcloud to inspect LangTut Google Cloud projects, billing budgets, Text-to-Speech quotas, and Cloud Storage, or configure and reauthenticate the local CLI.
---

# Google Cloud CLI for LangTut

Use the installed `gcloud` executable from the repo root. Check `command -v gcloud`,
`gcloud version`, and `gcloud <command> --help` rather than assuming a version or flags.
If missing on macOS with Homebrew, use `brew install --cask gcloud-cli` when installation
is authorized, then initialize with `gcloud init`.

## Login and project selection

```bash
gcloud auth list --format='table(account,status)'
gcloud config get-value project
gcloud auth login
```

For expired credentials or `invalid_grant`, run `gcloud auth login`, let the user
complete browser authorization, and wait for successful CLI completion. Verify access
with `gcloud projects describe <project-id>`. Use `gcloud auth login --no-launch-browser`
when a local browser cannot open; let the user handle authorization codes.

Prefer explicit `--project=<project-id>` flags. Discover the configured project and
confirm it belongs to LangTut; do not assume an unrelated default is the right target.
Change the persistent default with `gcloud config set project <project-id>` only when
requested or needed for the authorized setup.

CLI login and Application Default Credentials (ADC) are separate. Use
`gcloud auth application-default login` only when local application client libraries
need ADC; ordinary CLI inspection does not require it. Never print access tokens,
credential files, service-account JSON, or private keys. If a direct API request is
needed, capture its token in process memory and omit it from output and diagnostics.

The CLI writes logs and credentials under `~/.config/gcloud`; a sandbox permission
error there can require approved execution outside the sandbox, not a reinstall.
For Python compatibility warnings, check supported runtimes before updating the CLI
or configuring `CLOUDSDK_PYTHON`; do not change the app's Python environment to fix gcloud.

## LangTut boundaries

Read [architecture.md](../../docs/architecture.md) and [audio.md](../../docs/audio.md)
before changing application authentication or audio behavior.

- TTS and GCS caching live in `app/services/tts.py`. The default audio bucket is
  `langtut-tts` in `settings.toml`; runtime `LANGTUT_*` overrides can select another bucket.
- Local clients use `google_cloud_service_account_file_path` when configured, otherwise
  ADC. Railway supplies `LANGTUT_GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` for production.
- User OAuth for Sheets is separate from CLI login and the TTS/GCS service account.
  Reauthenticating gcloud does not rotate production credentials or repair user sessions.
- Do not read secret payloads to discover project IDs. Use CLI project metadata and
  bucket metadata. Do not import `run.py` or the TTS singleton for operational checks.

## Useful read-only checks

Replace placeholders with discovered identifiers; avoid committing personal account IDs.

```bash
gcloud projects describe <project-id> --format='yaml(projectId,projectNumber,name,lifecycleState)'
gcloud services list --enabled --project=<project-id> --format='table(config.name)'
gcloud billing projects describe <project-id>
gcloud billing budgets list --billing-account=<billing-account-id> --format=json
gcloud storage buckets describe gs://<audio-bucket> --format=json
gcloud storage buckets get-iam-policy gs://<audio-bucket> --format=json
```

Inspect bucket access, lifecycle rules, and public access prevention without downloading
audio or listing user-specific object paths unless relevant to the request.

For TTS effective quotas, check `gcloud beta quotas info list --help` before using
`--service=texttospeech.googleapis.com --project=<project-id>`. Older installations may
lack the beta component. A read-only alternative is the Service Usage REST endpoint:

```text
GET https://serviceusage.googleapis.com/v1beta1/projects/<project-number>/services/texttospeech.googleapis.com/consumerQuotaMetrics?view=FULL
```

Follow pagination and compare each bucket's `effectiveLimit` with `defaultLimit`.
Report the project's actual values rather than treating documentation defaults as its settings.

## Billing and changes

A disabled Budget API blocks CLI budget inspection; it does not prove alerts are absent.
Report that limitation and use the billing console when appropriate. Do not accept
automatic API-enablement prompts during a read-only check.

Ordinary budgets send alerts, not guaranteed spending cutoffs. TTS quotas limit request
rates rather than monthly euros. Native spend caps cover only eligible services; verify
the current list before suggesting one for TTS or GCS. Budget notifications can trigger
automatic billing removal, but reporting delays allow overshoot and disabling billing
can cause irreversible resource/data loss. Never promise an exact project-wide ceiling.
Use the billing account's currency for proposed budgets.

Prepare concrete changes and obtain explicit user confirmation immediately before
production mutations: API enablement, quota changes, budget/automation creation,
IAM changes, credential rotation, bucket changes/deletion, or billing unlinking.
Preserve existing GCS data when designing spending controls.

References: [CLI initialization](https://docs.cloud.google.com/sdk/docs/initialize),
[TTS quotas](https://docs.cloud.google.com/text-to-speech/quotas),
[spend caps](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps),
[billing shutdown](https://docs.cloud.google.com/billing/docs/how-to/disable-billing-with-notifications).
