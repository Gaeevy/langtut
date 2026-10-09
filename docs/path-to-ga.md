# Path to GA

Status: proposal for discussion, not an approved implementation specification.
Last updated: 2026-10-03.

## Goal and recommended direction

Make LangTut usable by someone who has no spreadsheet, no prepared vocabulary, and no knowledge
of the project's internals. A user should be able to find useful content, study it, trust that
progress is saved, and return later to continue.

The long-term goal includes an iPhone app available in the App Store. The recommended sequence is
to establish a self-contained web product first, validate it with a small beta, and reuse its
Python backend for an iPhone client. Web general availability (GA) and App Store release are
separate milestones; neither needs to block the other.

Keep Flask, SQLAlchemy, Jinja, and vanilla JavaScript initially. Move vocabulary and progress into
the application database, make Google Sheets an optional import source, and separate application
identity from permission to access Google APIs. Build reusable services without requiring a full
mobile API or a new frontend framework at the start.

## Current state

The current architecture is documented in [architecture.md](./architecture.md), with playback
details in [audio.md](./audio.md).

| Area | Existing behavior | Challenge for general users |
|---|---|---|
| Vocabulary | Google Sheets stores words, examples, levels, and statistics | Users must prepare and maintain a specially structured spreadsheet |
| Authoring | Manual spreadsheet editing or externally generated content pasted into Sheets | No guided content creation or validation within LangTut |
| Identity | Google OAuth establishes the user and provides Google API credentials | Studying is coupled to a Google integration even when that integration is unnecessary |
| Learning | Reusable services manage modes and answer evaluation; active state lives in server sessions | Durable session recovery and device-independent sessions need explicit design |
| Progress | Learn/review flows batch progress back to Sheets at session completion or early exit | An interrupted session is not equivalent to incrementally committed progress |
| Interface | Server-rendered pages with some JSON endpoints | A native client needs a more complete, consistent data API |
| Persistence | SQLite already stores users, spreadsheet links, tokens, and verbs | Vocabulary migration and schema evolution need a migration process; `create_all()` is insufficient |
| Mobile | Responsive assets, an app manifest, browser audio workarounds, and a service worker | Home-screen polish and real-device validation are needed; offline study is not implemented |
| Operations | Railway configuration expects persistent storage for SQLite and sessions | Backups, restoration, support, capacity, and launch monitoring need verified procedures |

The local assessment on 2026-10-03 ran 166 passing tests, with Flask-Session deprecation warnings.
This is a baseline, not proof of production readiness, security, or real-device audio behavior.
Production operations and a physical iPhone were not inspected in that assessment.

## Challenges, options, and tradeoffs

### 1. Own vocabulary and progress in the application

**Options**

- Keep Sheets as the primary store and add a friendlier editor. This reduces the initial migration
  work but retains Google permission requirements, remote-call failures, and spreadsheet-specific
  assumptions throughout the product.
- Move to SQLite. This builds on the existing stack and makes content and progress locally
  transactional. It requires persistent storage, backups, deliberate write concurrency, and care
  when scaling beyond one application instance.
- Move directly to a managed PostgreSQL database. This better supports multiple application
  instances and concurrent writers, but adds operational and migration work before demand is known.

**Recommendation:** use SQLite for the first self-contained release, behind SQLAlchemy and service
boundaries. Revisit PostgreSQL when measured contention, deployment topology, or availability
requirements justify it. Becoming an iPhone app does not itself require changing databases.

Separate these concepts in the proposed model:

| Concept | Responsibility |
|---|---|
| User | Application identity and preferences |
| Login identity | Association between a user and a sign-in provider |
| Vocabulary set | Owner, title, target language, translation language, and lifecycle status |
| Card | Word/phrase, translation, examples, notes, and content provenance |
| User card progress | User/card association, level, counters, and study timestamps |
| Study session and answers | Durable session state and accepted answers needed for resume and retry handling |
| Import record | Source identifiers and mappings needed to make migration repeatable |

These are conceptual boundaries, not a final table specification. Keep content separate from
progress even if all initial sets are private. Existing irregular-verb data should be preserved;
unifying it with vocabulary is a separate decision.

**Open questions:** Can a card belong to multiple sets? Does copying a set create independent
cards? Which edits reset progress? How long should answer history be retained? Does archiving a
set hide it from study while retaining progress? What happens to an active session when a card
is edited or deleted?

### 2. Replace spreadsheet authoring with a small, complete editor

Use “set” or “deck” in the product rather than “tab.” Offer creation, renaming, card editing,
archiving, and deletion. Validate required fields and language settings, and make validation
errors understandable without exposing internal schema details.

**Options:** a simple card form is easier to build and use on a phone; a spreadsheet-like bulk
editor is faster for experienced authors but increases frontend complexity. CSV import can serve
bulk users before a sophisticated editor exists.

**Recommendation:** start with a set list, a card list, and a simple card editor, plus a practical
bulk import route. Preserve the existing Jinja/form approach and progressively enhance it where
useful. Public sharing and collaborative editing can wait.

**Open questions:** Which card fields are mandatory? Should incomplete cards be saved as drafts?
Is undo sufficient for deletion, or is an archive/trash required? Are duplicate words allowed
when they have different meanings? Which language pairs will the first release support?

### 3. Give new users useful content immediately

Manual authoring alone still asks users to invest effort before experiencing the product.

**Options:** curated starter sets offer predictable quality but require editorial work; AI-generated
sets provide flexibility but introduce latency, cost, and quality variation; an empty editor is
cheap to build but creates the highest onboarding burden.

**Recommendation:** provide at least a small selection of reviewed starter sets for the initial
audience, alongside manual creation. Copy a starter set into the user's library initially so
editing behavior is straightforward. Decide later whether shared, centrally updated content is
worth the additional versioning and progress-mapping complexity.

**Open questions:** Who is the first audience and proficiency level? Is European Portuguese the
initial focus? Can users try studying before registering? Who reviews starter content and confirms
its reuse rights? What indicates successful onboarding: starting a session, completing one, or
returning for another?

### 4. Generate drafts inside the product

Accept topic/instructions, optional seed words or phrases, target language and regional variant,
translation language, proficiency, and requested size. Return a draft the user can inspect,
edit, and accept. Generation should not silently replace existing content.

**Options:** synchronous generation is simpler for small requests but vulnerable to request
timeouts; durable background jobs support longer requests, retry, and reconnection at the cost
of job infrastructure. Choose based on measured provider latency and the promised set sizes.

**Recommendation:** begin with bounded requests and structured, validated results. Preserve the
request and distinguish pending, failed, and completed generation. Prevent duplicate saved sets
when a user retries. Validate missing fields and duplicates, and make it clear that generated
language can need correction. Add per-user limits and track generation and TTS costs before
opening access broadly.

Grammar requests need a scope boundary: vocabulary phrases illustrating a grammar concept fit
the existing card model more directly than dedicated conjugation, explanation, or grammar tests.
AI-generated grammar exercises should not be assumed to work with the existing answer checker.

**Open questions:** Is AI generation required for the first beta or for GA? Which provider and
quality evaluation will be used? Can users regenerate individual cards? What happens to partial
results? What usage allowance is sustainable? Which user content is sent to the provider and
what retention/disclosure policy applies?

### 5. Separate identity from Google Sheets access

Removing Sheets does not require removing Google sign-in. Application authentication should
identify a user without requiring valid Sheets credentials. Google permissions should be requested
only when the user chooses to import from Google.

**Options**

- Retain Google as the only initial login: least interface change, but still excludes people who
  do not want a Google account.
- Add email links/codes: avoids managing passwords, but depends on reliable email delivery and
  careful expiry, rate limiting, and recovery behavior.
- Use a managed identity service: reduces custom authentication work, but adds provider dependency,
  pricing, and an integration/migration decision.
- Build password authentication: familiar to users, but adds password storage, verification,
  recovery, and abuse-prevention responsibilities.

**Recommendation:** first decouple the application's user/session from Google API authorization.
Then select an authentication approach based on the initial audience and future iOS needs. Avoid
building a password system merely to remove Google. Link additional identities only through a
verified flow; matching an email string alone is not a sufficient account-linking design.

Include logout, recovery, account deletion, and a defined data-retention policy. Review ownership
checks for every content/progress endpoint, cookie and CSRF handling for browser mutations, and
rate limits for expensive or abuse-prone operations before public release.

**Open questions:** Must the first public release support a non-Google login? What does account
deletion remove from audio caches, imports, and backups? How are existing Google users preserved?
How will a user link or unlink a provider without losing access?

### 6. Make progress durable and migration reversible

Persist accepted study actions incrementally. Retrying the same answer after a connection failure
must not apply its effects twice. Store enough durable state to resume after a restart, and define
the behavior when the same session is opened on two devices.

Database-backed session records offer stronger recovery than keeping the authoritative queue only
in a filesystem login session, but require explicit session identifiers and concurrency rules.
Initially, supporting one active study session per user may be simpler than merging concurrent
sessions. Keep browser authentication state behind `SessionManager` as required by the project.

For the Sheets transition:

1. Add versioned schema migrations and take a restorable backup before backfills.
2. Import into the new model with mappings from workbook, worksheet, and card identifiers.
3. Report invalid rows and reconcile card counts, content, levels, and statistics.
4. Test that a repeated import does not duplicate data or overwrite newer progress unexpectedly.
5. Cut over a small group and verify studying, editing, recovery, and rollback procedures.
6. Make Sheets import-only after cutover; avoid indefinite bidirectional synchronization.

A rollback must account for new edits and answers written after cutover. Restoring an old database
alone would discard them. Define the rollback window and reconciliation procedure before migration.

**Open questions:** Should reimport update existing cards, create a new set, or offer a preview?
Should it ever overwrite progress? How are missing or duplicate source IDs resolved? How much
simultaneous web/mobile studying must the first release support?

### 7. Prepare for iPhone without making it the first dependency

| Option | Benefit | Cost or limitation |
|---|---|---|
| Home-screen web app | Maximum reuse; quickest improvement for iPhone users | Browser lifecycle/audio constraints; no App Store listing |
| WebView wrapper | Reuses much of the current interface | Authentication handoff and native integrations still need work; review risk for a minimal wrapper |
| Native client | Direct control over iPhone UI, audio, and device integration | New client implementation and mobile skills; backend needs a complete API |

**Recommendation:** polish the mobile web experience first. Fix the missing manifest icons and
review service-worker scope and caching before expanding its control over authenticated pages.
Do not indiscriminately cache personalized pages or state-changing requests. Follow the physical
device checklist in [audio.md](./audio.md). Home-screen installation does not imply offline study.

For a native client, reuse Flask services through JSON endpoints for set selection, session
creation, questions, answers, and results. Provide consistent authentication errors and safe
retries. A full API can follow the beta; clear service boundaries should begin earlier.

If listening with the screen locked is a primary reason to build iOS, prototype login, selecting
a set, and native background audio before rebuilding the entire interface. Test interruptions,
headphones, reconnection, and session expiry on a real device.

Offline study is a separate feature: it needs local content/audio storage, queued answers,
reconciliation, and conflict rules. Defer it unless essential to the initial audience.

**Open questions:** What user need justifies installing the native app? Is background listening
required? Is Android also a goal? Must settings and authoring be available natively at launch?
Will the product charge users, and how does the chosen distribution affect purchasing flows?

Platform references checked during the initial assessment; recheck before implementation and
submission because requirements can change:

- [Apple home-screen web apps](https://support.apple.com/en-lamr/guide/iphone/iphea86e5236/ios).
- [Google OAuth policy](https://developers.google.com/identity/protocols/oauth2/policies): Google
  authorization cannot simply run inside a developer-controlled embedded browser.
- [Apple audio sessions](https://developer.apple.com/documentation/AVFAudio/AVAudioSession): native
  audio configuration is part of a background-listening implementation.
- [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/): assess minimum
  functionality (4.2), login options and exceptions (4.8), and account deletion (5.1.1). A wrapper
  is not guaranteed acceptance. Removing Sheets may also change whether a third-party-service
  login exception is relevant.

### 8. Operate a public service sustainably

GA includes operational readiness, not just completed screens. Verify backup restoration, database
migrations, error visibility, support/reporting, and behavior when TTS or generation is unavailable.
Monitor actionable failures without logging credentials or unnecessary user content.

Track a small number of product measures: first-session completion, returning learners, failed
study saves, generation failures, audio failures, and external-service cost. Define the audience
and privacy implications before adding analytics tooling.

**Open questions:** Is launch free, invite-only, or paid? What monthly cost ceiling is acceptable?
Who responds to support requests and incidents? What loss-of-data and recovery windows are
acceptable? What load must be tested before removing beta limits?

## Suggested execution order

Each phase should end in a usable increment with an explicit acceptance check. Estimates should
follow scope decisions; offline support, sharing, and custom authentication can change effort
substantially.

| Phase | Deliverable | Acceptance check |
|---|---|---|
| 0. Define the first release | Initial audience/languages, vocabulary scope, login direction, AI requirement, and budget | A short agreed scope with explicit exclusions and success measures |
| 1. Establish persistence | Migration tooling, content/progress model, ownership rules, backup/restore, repeatable Sheets import | Existing content and progress reconcile in a test migration; restore and reimport are demonstrated |
| 2. Switch the study engine | Database-backed learning/review/listening, durable progress, safe retries, recoverable sessions | Study without Sheets calls; interruption/retry tests pass; current learning behavior is preserved |
| 3. Complete web authoring and onboarding | Set/card editor, starter sets, import/export, mobile layout | A new user can create or choose content and finish studying without a spreadsheet |
| 4. Complete account lifecycle | Google API access made optional, selected login options, recovery/linking/deletion | An ordinary study session needs no Google API token; ownership and account lifecycle checks pass |
| 5. Add AI drafts | Guided request, validation, preview/edit/save, failure recovery, usage controls | Representative prompts produce useful editable drafts; retries and failures do not lose input or duplicate sets |
| 6. Run a limited beta | Invited users, real-device checks, support channel, cost/error monitoring | Observed problems are addressed; users return; save reliability and cost remain within agreed limits |
| 7. Release web GA | Resolve beta blockers, complete operational and user-facing readiness | Meet the GA checklist below and make an explicit release decision |
| 8. Build and release iOS | Consistent mobile API, authentication handoff, chosen client, audio prototype, device testing and submission | Core journeys pass on devices and current App Store requirements are addressed |

Phases overlap selectively: identity design belongs in phase 0/1 even if additional login methods
ship in phase 4. Authorization tests accompany every endpoint. Durable progress belongs in phase 2,
not in final hardening. A manual/starter-set beta can start before AI if AI is not a launch promise.
An iOS audio feasibility prototype can happen earlier if background listening is decisive.

Implementation must update [architecture.md](./architecture.md) and the persistence rules in
[AGENTS.md](../AGENTS.md) when the new storage boundary actually changes. This proposal does not
change those rules today. Each schema change requires a migration/backfill plan. Production
mutations still require the confirmation specified by the repository instructions.

## Proposed web GA checklist

- A new user can get a useful set and complete a session without Sheets or external AI tools.
- Users can create, edit, archive/delete, and export their vocabulary with clear progress semantics.
- Restarting, retrying, or losing connectivity does not silently duplicate or discard acknowledged answers.
- Users cannot read or change another user's private content or progress.
- Chosen login methods, recovery, logout, and account deletion work end to end.
- Existing content and progress have a verified migration and reconciliation path.
- Backups have been restored successfully; migration and rollback procedures have been exercised.
- Core learning, review, and listening flows pass automated checks and real-device mobile checks.
- AI/TTS failures have understandable outcomes, and usage limits keep spending within the chosen budget.
- Privacy/support information, incident ownership, and actionable monitoring are in place.
- Beta feedback and agreed success measures support opening access more broadly.

## Deliberately deferred unless validated as essential

Public set marketplaces, collaborative editing, bidirectional Sheets synchronization, a full
grammar-course engine, offline answer synchronization, Android, and a frontend framework rewrite.
PostgreSQL is a deployment decision to revisit with evidence, not a prerequisite for mobile or GA.

## Decisions to resolve first

1. Who is the first user, and which language/level is the first release designed for?
2. Is AI generation a GA requirement, or can manual editing and starter sets establish value first?
3. Must non-Google login be available at the first public release?
4. Are all initial sets private copies, including starter sets?
5. Is background listening important enough to bring an iOS prototype forward?
6. What usage budget, pricing approach, and reliability targets define a sustainable launch?
