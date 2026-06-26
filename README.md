# ccmigrate

`ccmigrate` is a local-first CLI for collecting agent chat history from Claude Code, Codex, and opencode into one portable archive.

It is designed for people who switch between coding agents and do not want project context, decisions, and prior debugging history stranded in one tool.

## What it does

`ccmigrate` deliberately avoids writing back into provider-owned history stores. Those formats are private and can change. Instead, it:

- discovers local provider chat stores
- normalizes conversations into a canonical JSONL archive with text turns, tool calls, and plan content
- exports provider-friendly Markdown and JSONL bundles
- generates `CLAUDE.md`, `AGENTS.md`, and `OPENCODE.md` memory files that can be copied into another project

## Install

```bash
python3 -m pip install -e .
```

Or run without installing:

```bash
python3 -m ccmigrate doctor
```

## Quickstart

```bash
ccmigrate doctor
ccmigrate scan
ccmigrate list
ccmigrate sync
ccmigrate export
ccmigrate dump --project my-app --zip
```

Generated files are written to `.ccmigrate/` by default.

## Commands

```bash
ccmigrate doctor
ccmigrate scan
ccmigrate list --providers codex --project my-app
ccmigrate sync
ccmigrate sync --dry-run --redact
ccmigrate export --format markdown
ccmigrate export --format provider-memory
ccmigrate dump --project my-app --limit 1 --zip
```

### `doctor`

Checks which provider roots exist and how many conversations can be discovered.

### `scan`

Prints provider roots and discovered conversation counts. Use `--json` for machine-readable output.

### `list`

Lists conversations with recency, project, message count, and tool-call count:

```bash
ccmigrate list --providers claude codex --project my-app --limit 10
ccmigrate list --json --since 2026-06-01
```

### `sync`

Reads provider stores and writes the canonical archive:

```bash
ccmigrate sync --providers claude codex opencode
ccmigrate sync --project my-app --since 2026-06-01 --redact
ccmigrate sync --dry-run
```

### `export`

Creates portable outputs from the canonical archive:

```bash
ccmigrate export --format all
ccmigrate export --format markdown
ccmigrate export --format jsonl
ccmigrate export --format provider-memory
ccmigrate export --project my-app --redact
```

### `dump`

Creates a shareable thread bundle directly from local provider history. Redaction is enabled by default.

```bash
ccmigrate dump --project my-app --limit 1 --zip
ccmigrate dump --id <conversation-id> --out /tmp/thread-dump --zip
ccmigrate dump --project my-app --since 2026-06-01 --limit 5 --note "handoff context"
```

For safety, `dump` refuses to run unless you pass a selector (`--project`, `--since`, `--id`) or explicitly pass `--all`. Use `--no-redact` only for trusted private sharing.

## Output

```text
.ccmigrate/
  conversations.jsonl
  manifest.json
  export/
    conversations.md
    conversations.jsonl
    CLAUDE.md
    AGENTS.md
    OPENCODE.md
ccmigrate-thread-dump-*/
  README.md
  manifest.json
  conversations.jsonl
  threads.md
  threads.jsonl
```

## Canonical schema

Each line in `.ccmigrate/conversations.jsonl` is one conversation:

```json
{
  "schema_version": "2",
  "id": "stable-id",
  "provider": "claude",
  "source_path": "/path/to/provider/file",
  "project": "/path/to/project",
  "title": "session title",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:01Z",
  "messages": [
    {
      "id": "message-id",
      "role": "user",
      "content": "message text",
      "created_at": "2026-01-01T00:00:00Z",
      "metadata": {}
    }
  ],
  "tool_calls": [
    {
      "id": "tool-call-id",
      "name": "Bash",
      "input": {"command": "pytest"},
      "result": "tests passed",
      "created_at": "2026-01-01T00:00:01Z",
      "metadata": {}
    }
  ],
  "plan_content": "optional markdown plan",
  "metadata": {}
}
```

## Provider paths

Defaults are based on common local installs:

- Claude Code: `~/.claude/projects`
- Codex: `~/.codex/sessions`
- opencode: `~/.local/share/opencode/storage`

Use `--home` to point at a different home directory, or provider-specific flags:

```bash
ccmigrate sync --claude-root /path/to/.claude/projects
ccmigrate sync --codex-root /path/to/.codex/sessions
ccmigrate sync --opencode-root /path/to/opencode/storage
```

## Design notes

This tool preserves raw metadata per message/tool call, but the portable archive schema only relies on stable fields: provider, project, session id, timestamps, text content, canonical tool names, tool inputs/results, and plan content.

The provider-memory export uses `AGENTS.md` as the shared bridge file. Claude Code can import `AGENTS.md` from `CLAUDE.md`, and opencode initializes projects with `AGENTS.md`.

`ccmigrate` is inspired by existing migration tools, but this MIT project is implemented clean-room. It does not copy code from projects with incompatible licenses.

See [docs/RESEARCH.md](docs/RESEARCH.md) for source notes.

## License

MIT
