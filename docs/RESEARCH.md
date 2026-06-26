# Research Notes

This project targets portable context and archive generation rather than direct mutation of provider-owned chat databases.

## Findings

- Claude Code documents `CLAUDE.md` and auto memory as the two systems that carry knowledge across fresh context windows. Claude also documents that `CLAUDE.md` can import `AGENTS.md`, which makes `AGENTS.md` a practical bridge file.
- AGENTS.md is a plain Markdown convention for repository-level agent instructions. It is designed to include project overview, build/test commands, style, testing, security, and other context that would normally be re-explained to an agent.
- OpenCode documents `/init` as generating an `AGENTS.md` file and recommends committing it so OpenCode can understand the project structure and coding patterns.
- OpenCode also documents project and global config locations, but these are configuration inputs rather than transcript import APIs.
- Codex CLI is open source and runs locally. The public repository and AGENTS.md ecosystem make `AGENTS.md` the safest common denominator for Codex-facing project memory.
- builderpepc/agent-migrator demonstrates a more aggressive native migration model: adapter-based read/write/delete, first-class text/tool turns, plan preservation, and project-scoped listing. Its package metadata and LICENSE file identify the project as CC-BY-SA-4.0, so `ccmigrate` treats it as product/architecture research only and does not copy implementation code.

## Design Implications

- `ccmigrate sync` creates a canonical archive in `.ccmigrate/conversations.jsonl`.
- The canonical archive stores text messages, normalized tool calls, and optional plan content.
- `ccmigrate list` exposes project-scoped conversation inventory for scripting.
- `ccmigrate export` creates readable Markdown and typed transcript JSONL.
- `ccmigrate export --format provider-memory` creates `AGENTS.md`, `CLAUDE.md`, and `OPENCODE.md`.
- Direct provider history import should be a future opt-in feature only where a provider exposes a stable import API or a well-documented writable format. If implemented, it should create backups, use atomic writes, and support delete/rollback.

## Sources

- Claude Code memory docs: https://code.claude.com/docs/en/memory
- AGENTS.md format: https://agents.md/
- OpenCode intro and `/init`: https://opencode.ai/docs/
- OpenCode config locations: https://opencode.ai/docs/config/
- OpenAI Codex repository: https://github.com/openai/codex
- agent-migrator repository: https://github.com/builderpepc/agent-migrator
