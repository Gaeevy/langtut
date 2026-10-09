# AI-native vocabulary and MCP MVP

Status: proposed implementation plan; individual design decisions remain open.
Last updated: 2026-10-06.

## Purpose and priorities

LangTut serves two immediate purposes: personal language practice and learning AI-assisted
software development. ChatGPT is already part of the language-practice and vocabulary-authoring
workflow. Preserving that integration is a core MVP requirement when moving vocabulary from
Google Sheets to SQLite.

The first audience is the current primary user, followed by a few invited family testers. Public
GA is a possible later milestone. This plan narrows the broader [Path to GA](./path-to-ga.md)
around that audience; it does not require completing the entire GA roadmap first.

The defining journey is:

> In ChatGPT, inspect vocabulary and examples across my sets, generate additional material, save
> it into LangTut, and study it. Restarting the app preserves acknowledged progress, and retrying
> a save does not create another copy of the batch.

Do not switch the production vocabulary store until this journey works with the new database
and authenticated MCP connection.

## Target architecture

```text
Browser -> Flask routes -------------------+
                                          |
ChatGPT -> authenticated MCP adapter ------+-> vocabulary/study services
                                                |
                                                v
                                         SQLAlchemy -> SQLite

Google Sheets -> explicit import -> vocabulary services/database
```

MCP advertises named tools with descriptions and structured input schemas, accepts tool calls,
and returns structured results. It is an adapter to application capabilities, not a database
connection for the model. Do not expose arbitrary SQL, filesystem access, or model-selected
user identities.

Retain Python, Flask, SQLAlchemy, Jinja, vanilla JavaScript, Google sign-in, and the existing TTS
infrastructure initially. Prefer one Railway deployment with one persistent database volume.
The MCP adapter and web interface should share application services and ownership rules.

The current [Architecture](./architecture.md) documents implemented behavior. This proposal does
not change its persistence or authentication boundaries until implementation actually lands.

## Phase 1: Prove ChatGPT connectivity

### Deliverable

A small MCP prototype using disposable vocabulary, connected to the primary user's ChatGPT
account. Demonstrate discovery, reading a set, and adding a card before investing in the full
storage migration.

### Implementation considerations

- Use an MCP SDK for protocol handling. Prefer Streamable HTTP for the remote connection.
- Define explicit schemas, bounded results, and useful tool descriptions. A JSON REST endpoint
  by itself is not an MCP server.
- Initially use synthetic data and a development endpoint. Authenticate before exposing real
  private content or production writes.
- Check the current account's ability to create and use a custom MCP connection. Verify the
  exact ChatGPT surfaces used for language practice, including mobile if required. Official
  custom-connection documentation describes setup on the web; do not infer mobile support.
- Test MCP independently with an inspector, then test actual prompts in ChatGPT. Tool discovery
  does not prove that the model will select the intended tool or supply valid inputs.
- Evaluate Python SDK/runtime integration with Flask early. An ASGI MCP component may need an
  adapter or a combined runtime; preserve correct streaming and Flask application-context
  handling. Do not assume an ordinary Flask blueprint can host every SDK unchanged.
- Keep development endpoints separate from production and avoid committing credentials.

### Acceptance check

ChatGPT can retrieve synthetic vocabulary and save a synthetic card through the advertised
tools. Document account/surface limitations and the chosen runtime arrangement.

## Phase 2: Establish persistence and reusable services

### Deliverable

Versioned schema migrations, an initial vocabulary model, and services reused by web and MCP
entry points. Application identity works independently of Google Sheets permissions.

### Initial model

| Concept | Initial responsibility |
|---|---|
| Existing user | Stable application identity; preserve existing user IDs |
| Vocabulary set | Owner, title, language pair/variant, timestamps, archived status |
| Card | Set, word/phrase, translation, equivalent, examples, notes, provenance |
| User card progress | User/card association, level, counters, last studied timestamp |
| Import mapping | Source workbook/worksheet/card identity mapped to application records |
| Saved operation | Per-user request identity and result for retry-safe mutations |

Start with private sets and one set per card. Copying a set can create independent cards later.
Separate content from progress even while all content is private. Preserve existing verb tables
and behavior; unifying verbs and vocabulary is outside this migration.

### Implementation considerations

- Add Alembic, optionally through Flask-Migrate. Establish a verified baseline for the existing
  schema before adding tables. Only stamp a database after checking it matches that baseline;
  do not rerun initial table creation against an existing installation.
- Review generated migrations, especially SQLite table rebuilds, constraints, and backfills.
  Test both a fresh installation and upgrading a copy of an existing database.
- Introduce vocabulary services with typed inputs/results and explicit acting-user context.
  Keep request parsing in routes/adapters and SQLAlchemy queries in application services.
- Enforce ownership for every set/card lookup and mutation, including searches and batches.
  Never accept a model-supplied user ID as authority.
- Add stable IDs and indexes for ownership, set membership, language, and timestamps. Define
  foreign-key enforcement and deletion behavior explicitly.
- Define content validation and duplicate policy. The same word can have different meanings;
  identical word strings are not necessarily invalid duplicates.
- Keep Google sign-in initially, but change ordinary application authentication to rely on a
  valid application session/user rather than a currently usable Sheets access token. Request
  Google API permissions for import separately and preserve existing account associations.
- Continue using `SessionManager` for browser session state. MCP requests use their verified
  token identity rather than borrowing browser cookies or active-set session state.

### Decisions to settle

Required card fields; language/voice settings per set; archive versus delete; whether edits reset
progress; normalized duplicate matching; scope of initial search; and account mapping for MCP.

### Acceptance check

Services can create, retrieve, search, and update private vocabulary in SQLite. Two test users
cannot access each other's records. Fresh-install and existing-schema migration tests pass,
and ordinary sign-in/studying no longer requires Sheets credentials once switched over.

## Phase 3: Import vocabulary and switch study flows in development

### Deliverable

A repeatable Sheets importer and database-backed learn, review, and listening flows, plus a
small web interface for inspecting/correcting cards and exporting vocabulary.

### Implementation considerations

- Import all existing card fields and statistics, along with per-workbook language settings.
  Report invalid rows, missing/duplicate source IDs, timestamp conversion problems, and counts.
- Scope source identity by workbook and worksheet, not only the row's card ID. Row numbers are
  unstable when a sheet is reordered. Decide how sources without reliable IDs are handled.
- Reimport must not duplicate records or silently overwrite newer content/progress. Record
  source mappings and define whether updates require a preview or explicit import mode.
- Refactor direct Sheets calls in learning, review, listening, dashboard, and selection flows.
  Use stable set IDs instead of tab names as authoritative identifiers.
- Persist accepted progress incrementally. Use a stable answer/operation ID so a retried answer
  applies once, including the case where a write succeeds but the response is lost.
- Existing filesystem-backed study queues may remain initially. Define the behavior after a
  restart or expired session: saved progress survives even if the queue must be recreated.
  Full session recovery and simultaneous-device queue merging can follow later.
- Progress updates must not write stale session copies over vocabulary edits made through MCP.
  Update progress separately from content. Define what happens when active-session cards are
  edited, archived, or deleted; restricting these operations initially is an acceptable option.
- Preserve both form and AJAX answer paths, Jinja/JavaScript contracts, and learning modes.
- Replace spreadsheet-based TTS cache namespaces with stable application identifiers. Preserve
  language/voice selection, invalidation ownership checks, and mobile gesture behavior. Follow
  [Audio System](./audio.md), including its manual browser checklist.
- A minimal editor is useful for fixing generated content. Avoid a full spreadsheet-style UI;
  provide set/card listing, basic edits, archiving, and a practical export format.

### Acceptance check

Imported content and progress reconcile with the source. Repeating an import follows the chosen
policy without duplication. Study/review/listening work without Sheets calls; retries do not
double-count progress; restart preserves committed results; frontend and physical-device audio
checks pass. Existing verbs continue to work.

## Phase 4: Complete authenticated MCP authoring

### Deliverable

A production-ready private connection for the primary user, backed by the new vocabulary
services. Other invited users can subsequently connect their own accounts to the same server.

### Initial tool contract

| Tool | Purpose and boundaries |
|---|---|
| `list_sets` | List owned sets with language, size, and timestamps; support recent ordering |
| `get_cards` | Retrieve a selected set's content/examples with bounded pagination |
| `search_vocabulary` | Search words, translations, and examples across owned sets |
| `create_set` | Create a private set with explicit title and language settings |
| `add_cards` | Validate and transactionally save a bounded batch to an owned set |

Recent vocabulary can be a search/list filter. Define whether "recent" means created, edited,
or studied; these answer different questions. The last five sets provide useful context but
cannot prove a candidate is absent from older sets. Cross-set search and server-side duplicate
checks remain necessary. Basic normalized/text search is sufficient initially; embeddings are
optional future work.

### Authorization work

- Use OAuth authorization-code flow with PKCE and the MCP-required discovery metadata. Choose
  a compatible established provider/library early; do not hand-roll cryptography or assume
  that any Google login library also acts as an MCP authorization server.
- Distinguish Google authentication (who signed in), application account identity, and MCP
  authorization (what ChatGPT may do). Map a verified provider subject to an application user
  through an authenticated linking flow; matching an email alone is insufficient.
- Define `vocabulary:read` and `vocabulary:write` scopes. Validate token issuer, audience,
  expiry, and permissions before executing tools. Support expiry, reconnection, and revocation.
- Configure exact redirect URIs and the required resource/client-registration metadata for
  ChatGPT. Custom API-key headers are not a substitute for its supported OAuth flow.
- Keep private data protected even during read-only testing. Test two users, insufficient
  scopes, expired tokens, and attempts to supply another user's set/card IDs.
- Browser mutations retain appropriate CSRF protections; bearer-token MCP authentication is
  a separate entry point. Keep authorization enforcement shared at the service boundary.

### Tool reliability and behavior

- Return structured content, stable IDs, pagination cursors, and understandable errors. Make
  truncation explicit; a partial result must not look like the entire library.
- Bound query sizes, batch sizes, and request rates. Avoid logging tokens or complete private
  card batches. Treat vocabulary/examples as data, not instructions to execute.
- For initial batch insertion, prefer all-or-nothing validation with indexed field errors.
  Define duplicate warnings and any override behavior explicitly.
- Require a per-user idempotency key for writes. Store the request fingerprint and result in
  the same transaction as inserted cards. A repeated key with different input must fail;
  repeating the same request returns the original result. Define key retention.
- Describe read/write tools accurately and annotate their effects. Test prompts that inspect
  or generate content without requesting a save, so those conversations do not mutate data.
- Initially omit MCP deletion, progress manipulation, and expensive TTS/generation tools.
  ChatGPT can generate the vocabulary itself and submit it; a separate model call inside
  LangTut is unnecessary for that workflow.

### Acceptance check

In ChatGPT, search existing vocabulary/examples, create or select a set, and save new cards.
The web app can immediately study them. Invalid batches fail clearly, retries do not duplicate
cards, unauthorized requests fail, and disconnect/reconnect works. Verify actual client behavior
alongside automated service/protocol tests.

## Phase 5: Operational readiness and controlled cutover

### Deliverable

A verified Railway deployment and migration/restore procedure, followed by switching the
primary user's authoritative vocabulary store. Prepare operational work throughout earlier
phases; this phase is the release gate, not the first time backups are considered.

### Implementation considerations

- Add CI for relevant checks using `uv`: Ruff, the full pytest suite, and migration tests.
  Separate automated verification from production release approval. Preserve the repository's
  explicit confirmation requirement immediately before production mutations.
- Keep SQLite on the persistent `/app/data` volume and initially use one application instance.
  Multiple Gunicorn workers still mean concurrent writers: use short transactions, configure
  and test lock handling, and evaluate WAL/busy timeout with the actual workload.
- Run migrations once in a controlled startup step before serving traffic, not from each
  worker's import of `run.py`. Fail startup on migration errors and account for old processes
  still using the database. Prefer compatible additive changes during early rollout.
- Railway volumes are unavailable during build and pre-deploy steps. Migrations touching the
  volume need a runtime procedure after the volume is mounted.
- Verify the actual production mount, deployment configuration, and backup availability; local
  files describe intent, not proof of the deployed state.
- Set a backup frequency, retention, and acceptable loss window. Use a SQLite-consistent backup
  method; copying only a live main database file is unsafe when WAL contains committed data.
  Restore a backup into an isolated environment and check integrity and representative records.
- Keep a recoverable copy outside the live application volume. Securely preserve configuration
  needed for recovery, including encryption keys, without logging or committing secrets.
- Add health checks and actionable logs for database errors, failed saves, MCP authorization
  failures, imports, and TTS failures. Avoid private content and credential payloads.

### Cutover procedure

1. Rehearse import, migrations, study, MCP authoring, and restore against development data.
2. Back up the existing application database and preserve a source vocabulary snapshot.
3. Pause studying and editing in Sheets for the final import; reconcile content and statistics.
4. With explicit production confirmation, deploy/cut over and exercise the defining journey.
5. Keep the source Sheets intact as a reference; disable writes through the old study path.
6. Monitor saves, authentication, playback, and MCP behavior during initial personal use.

Define rollback before step 4. After cutover, new cards and answers exist only in SQLite;
restoring an old backup or returning to Sheets would lose those changes unless reconciled.
Specify a rollback window and an export/reconciliation procedure. Do not create indefinite
bidirectional synchronization to avoid making this decision.

### Acceptance check

Production content/progress reconcile, authenticated ChatGPT authoring and studying work,
deployment/restart preserves data, and backup restoration has been demonstrated. Update
`architecture.md`, `audio.md`, setup commands in `README.md`, and persistence rules in `AGENTS.md`
to match the implemented boundaries.

## Following milestone: invited family testing

Use the same database/server with separate accounts and private sets. Prove account isolation
before invitations, and document how testers connect ChatGPT, revoke access, import/export, and
report problems. Confirm each tester's ChatGPT account supports the required connection flow.

Keep content sharing separate from access control: family membership does not imply permission
to read another user's sets. Start with independent copies if sharing content is needed.

Revisit PostgreSQL when measured write contention, deployment topology, or availability needs
justify it. User count alone is not the trigger. Public directory distribution, GA account
lifecycle/support, pricing, and broader operational requirements follow demonstrated usefulness.

## Deferred from this MVP

Public plugin distribution, shared/collaborative decks, semantic vector search, in-product AI
generation, offline synchronization, full cross-device session recovery, and a native iPhone
client. These can reuse the service boundaries established here.

## First implementation decisions

1. Confirm the primary user's required ChatGPT surfaces and custom-connection access.
2. Select the Python MCP runtime integration and OAuth provider/library through a small spike.
3. Set initial card/set rules, duplicate semantics, and content/progress edit behavior.
4. Choose the migration baseline, import identity policy, and progress retry contract.
5. Define the production backup/restore and cutover/rollback procedure.

## External references

Checked for this proposal on 2026-10-06; recheck client and hosting requirements during
implementation.

- [Connect a custom MCP server to ChatGPT](https://developers.openai.com/api/docs/guides/custom-mcp-server)
- [MCP authentication requirements](https://developers.openai.com/plugins/build/auth)
- [MCP server and optional UI quickstart](https://developers.openai.com/plugins/build/app-quickstart)
- [Railway persistent volumes and runtime availability](https://docs.railway.com/volumes)
