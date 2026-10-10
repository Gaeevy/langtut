# Documentation

| Read this | For |
|---|---|
| [Project README](../README.md) | Installation and local startup |
| [Architecture](architecture.md) | Implemented runtime, persistence, and permissions |
| [Deployment](deployment.md) | Railway configuration, healthcheck, and variable commands |
| [MCP demo](mcp.md) | Tool contract and local/deployed testing |
| [Audio](audio.md) | Browser playback contracts, caching, device checks |
| [Agent guide](../AGENTS.md) | Coding conventions, tests, operational rules |
| [AI-native roadmap](ai-native-mcp.md) | Proposed private MCP and vocabulary migration |
| [Path to GA](path-to-ga.md) | Proposed onboarding, account lifecycle, mobile, release criteria |

## Learn MCP authentication

These five write-ups explain the proposed design in reading order; they do not
claim OAuth is already implemented:

1. [Basics: identity, permissions, and tokens](../path-to-auth-mcp/01-basics.md)
2. [The OAuth connection, step by step](../path-to-auth-mcp/02-oauth-flow.md)
3. [Accounts, ownership, and permissions](../path-to-auth-mcp/03-accounts-and-permissions.md)
4. [Implementing it in LangTut](../path-to-auth-mcp/04-implementation.md)
5. [Testing, rollout, and revocation](../path-to-auth-mcp/05-testing-and-rollout.md)

Private deployment identifiers and authentication procedures live in gitignored
`operations.local.md`. Roadmap proposals do not override implemented behavior or
repository instructions.
