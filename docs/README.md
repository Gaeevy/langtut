# Documentation

Each topic has one primary reference. Update that reference when behavior changes,
then link to it from setup guides and plans.

| Reference | Owns |
|---|---|
| [Project README](../README.md) | Local installation, credentials setup, and startup |
| [Architecture](architecture.md) | Current code, data ownership, login sessions, and Sheets connections |
| [Deployment](deployment.md) | Runtime configuration, auth migration/rollback, and release verification |
| [Audio](audio.md) | Playback contracts, caches, and physical-device checks |
| [MCP](mcp.md) | Public tool contract, smoke tests, and private-MCP remaining work |
| [Agent guide](../AGENTS.md) | Coding rules, verification commands, and operational permissions |
| [AI-native roadmap](ai-native-mcp.md) | Proposed vocabulary storage, import, and ChatGPT authoring work |
| [Path to GA](path-to-ga.md) | Proposed onboarding, product decisions, beta, and iPhone release gates |

Current-code documentation describes the checkout. Roadmaps describe proposed work.
Production status requires a deployment check. Gitignored `operations.local.md` owns
private targets and local CLI context; `credentials.md`, when present, records local
credential choices. Keep their private details out of tracked documentation.
