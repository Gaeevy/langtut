# AI-native vocabulary and MCP MVP

Status: proposed follow-on work. Reviewed against this checkout on 2026-11-17.
[Architecture](architecture.md) describes implemented behavior.

## Goal and existing foundation

The first audience is the primary user, followed by invited family testers. The MVP
supports this journey in ChatGPT.

> Inspect vocabulary and examples across my sets, generate material, save it into
> LangTut, and study it. Restarting preserves acknowledged progress, and retrying a
> save returns the original result.

The current checkout provides Streamable HTTP MCP with a public, read-only
spreadsheet-name demo, independent browser login, an optional Google Sheets
connection, and credential refresh that runs without a browser request. Private MCP,
SQLite vocabulary, and ChatGPT card writes remain proposed work. Production cutover
and real-client checks require separate verification.

Keep Flask, SQLAlchemy, Jinja, vanilla JavaScript, Google sign-in, and TTS initially.
Start with one deployment and SQLite volume. Web and MCP adapters should share
application services and ownership checks. [Path to GA](path-to-ga.md) owns broader
onboarding, public-release, and iPhone decisions.

After vocabulary cutover, both adapters use SQLAlchemy vocabulary services and
Google Sheets becomes an explicit import source. Expose named, schema-validated
capabilities; keep database, filesystem, and acting-user authority in application code.

## Delivery sequence

| Phase | Deliverable | Acceptance check |
|---|---|---|
| 1. Private connectivity | Authenticated MCP using disposable vocabulary | ChatGPT discovers tools, retrieves a set, and saves a synthetic card on the required client surfaces |
| 2. Vocabulary persistence | Migration baseline, content/progress tables, reusable services | Fresh-install and upgrade tests pass; two users remain isolated |
| 3. Development study cutover | Repeatable importer, SQLite study/review/listening, small editor/export | Source reconciliation, safe retries, restart durability, and device audio checks pass |
| 4. MCP authoring | Bounded private read/write tools | ChatGPT searches and saves material that the web app can immediately study |
| 5. Controlled release | Verified deployment, backup/restore, and rollback | The primary user's complete journey works after deployment and restart |

Build operational checks throughout the phases. Switch the authoritative vocabulary
store after the complete journey passes, including authenticated MCP authoring.

## Private connectivity and authorization

The public demo establishes the SDK/runtime path. The next connectivity spike must
verify authenticated reading and writing in a development environment. Test protocol
behavior independently, then test real prompts and the owner's required ChatGPT
surfaces. Record account and device limitations observed during those checks.

[MCP remaining work](mcp.md#private-mcp-remaining-work) owns OAuth/discovery, the Auth0
identity mapping, scopes, and client connection requirements. Reuse the established
provider and SDK libraries. Resolve the acting local user from the verified token
before calling a service. Tool inputs identify owned sets/cards. Browser active-set
selection and cookies belong to the web adapter.

## Vocabulary model and migration

| Concept | Initial responsibility |
|---|---|
| Existing user | Stable local identity; retain existing user IDs |
| Vocabulary set | Owner, title, language pair/variant, timestamps, archived state |
| Card | Set, word/phrase, translation, equivalent, examples, notes, provenance |
| User card progress | User/card association, level, counters, last-studied timestamp |
| Import mapping | Workbook/worksheet/card identity mapped to application records |
| Saved operation | Per-user request identity, fingerprint, and retry result |

Start with private sets and one set per card. Keep content and progress separate.
Preserve the independent irregular-verb tables and behavior. Define copying and
sharing later when an actual use case requires them.

Use Alembic, optionally through Flask-Migrate, for subsequent schema evolution.
Establish a verified baseline that includes the auth migration already present in
this checkout. Stamp an existing database only after verifying its schema. Review
SQLite rebuilds, backfills, constraints, foreign-key enforcement, and indexes for
ownership, membership, languages, and timestamps.

Services take typed inputs and explicit acting-user context. Check ownership for
individual records, searches, and batches. Set required fields and duplicate rules;
the same word can have different meanings. Set/card IDs stay stable across adapters.

## Import and study behavior

Import all existing card content, progress, and workbook language settings. Scope
source identity by workbook, worksheet, and card ID. Row numbers change when a sheet
is reordered. Report missing/duplicate IDs, invalid rows, timestamp failures, and
reconciliation counts. Choose an explicit policy for sources without reliable IDs.

Reimport must preserve newer application edits and progress unless the selected import
mode explicitly replaces them. Store source mappings and provide preview or explicit
update modes. Repeated imports follow the chosen policy without creating duplicates.

Use stable set IDs in dashboard, selection, learn, review, and listening operations.
Persist accepted answers incrementally with operation IDs so a lost response and
retry apply the answer once. Update progress independently of content, and define
what happens when a session's cards are edited, archived, or deleted.

Browser queues can remain in filesystem sessions initially. Committed progress must
survive restart even if the queue must be recreated. Define concurrent-device behavior
before promising full session recovery. Preserve form and AJAX paths and learning modes.

Provide set/card listing, basic edits, archiving, and a useful export format. Move TTS
cache namespaces to stable application IDs when Sheets stops owning vocabulary.
[Audio](audio.md) owns voice, invalidation, gesture, and device verification contracts.

## MCP tools and write reliability

| Tool | Behavior |
|---|---|
| `list_sets` | Owned sets with language, size, timestamps, and recent ordering |
| `get_cards` | A selected set's content/examples with bounded pagination |
| `search_vocabulary` | Words, translations, and examples across owned sets |
| `create_set` | A private set with explicit title and language settings |
| `add_cards` | A validated, transactional batch for an owned set |

Define whether recent means created, edited, or studied. Recent sets provide context;
cross-set search and duplicate checks cover the rest of the library. Start with text
search. Add embeddings only after demonstrating a need.

Return typed results, stable IDs, pagination cursors, explicit truncation, and clear
errors. Bound queries, batches, and request rates. Treat vocabulary as data. Describe
and annotate tool effects, and verify that inspection or draft-generation prompts
produce no writes until a save is requested.

For batch insertion, use all-or-nothing validation with indexed field errors and
explicit duplicate warnings/overrides. Store a per-user idempotency key, request
fingerprint, and result in the insertion transaction. Repeating the same request
returns that result; changing input under the same key fails. Set key retention.

Initially omit MCP deletion, progress editing, and expensive TTS/generation tools.
ChatGPT can generate material and submit it through the vocabulary tools.

## Release and rollback

Follow [deployment procedures](deployment.md) for runtime configuration, approvals,
and the existing auth cutover. A vocabulary cutover additionally needs these steps.

1. Rehearse vocabulary migrations, import, study, MCP authoring, and backup restoration.
2. Back up SQLite, retain a source vocabulary snapshot, and preserve recovery keys securely.
3. Pause Sheets study/editing for the final import and reconcile content and statistics.
4. Obtain production approval, deploy, and exercise the complete ChatGPT-to-study journey.
5. Keep source Sheets as a reference and retire writes through the former study path.
6. Monitor save failures, authentication, audio, and external-service costs.

Keep migrations outside concurrent workers and test lock handling. Assess WAL and
busy timeout with the workload. Define backup frequency, retention, acceptable loss,
and restoration time; keep a recoverable copy outside the live volume.

Set a rollback window and export/reconciliation procedure before cutover. New cards
and answers after cutover need reconciliation before returning to an older database
or Sheets. Avoid indefinite bidirectional synchronization.

## Decisions and later milestones

Settle required fields, language/voice settings, archive/delete behavior, edit effects
on progress, duplicate matching, initial search scope, importer update modes, and the
migration/idempotency contracts before implementing the corresponding phase.

For invited family testing, prove separate-account isolation and document connection,
revocation, import/export, and problem reporting. Invitations do not grant access to
another user's private sets. Use independent content copies initially if needed.

Revisit PostgreSQL when measured contention, deployment topology, or availability
requirements justify it. Defer public distribution, collaborative sets, vector search,
in-product AI generation, offline synchronization, complete cross-device recovery,
and a native client to the product decisions in [Path to GA](path-to-ga.md).
