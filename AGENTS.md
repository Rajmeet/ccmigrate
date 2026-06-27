# AGENTS.md

## Project

`ccmigrate` is a local-first MIT CLI for moving agent conversation context across coding tools.

The default product stance is safe export:

- read provider stores
- normalize conversations into `.ccmigrate/conversations.jsonl`
- export Markdown, JSONL, `AGENTS.md`, `CLAUDE.md`, and `OPENCODE.md`
- avoid writing provider-owned stores unless the user explicitly asks for native migration

## Commands

Run tests:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

List local provider stores:

```bash
PYTHONPATH=src python3 -m ccmigrate doctor
```

List project conversations:

```bash
PYTHONPATH=src python3 -m ccmigrate list --project /path-or-name --json
```

Export latest project conversation safely:

```bash
PYTHONPATH=src python3 -m ccmigrate sync --project /path-or-name --limit 1 --store /tmp/ccmigrate-latest
PYTHONPATH=src python3 -m ccmigrate export --store /tmp/ccmigrate-latest --out /tmp/ccmigrate-latest/export
```

Create a shareable thread dump:

```bash
PYTHONPATH=src python3 -m ccmigrate dump --project /path-or-name --limit 1 --out /tmp/thread-dump --zip
```

Dump behavior:

- Redaction is enabled by default.
- Use `--id <conversation-id>` for exact thread selection.
- Use `--no-redact` only when the user explicitly wants private, unredacted sharing.
- Inspect `threads.md` before sending the zip to someone.
- Delete temporary dumps after testing because they contain chat-derived content.

Create a compact handoff when a native migrated session is too large for Codex:

```bash
PYTHONPATH=src python3 -m ccmigrate handoff --project /path-or-name --limit 1
```

For an exact oversized thread:

```bash
PYTHONPATH=src python3 -m ccmigrate handoff --id <conversation-id> --project /path/to/project --recent-messages 30
```

Then start a fresh Codex session with the generated prompt:

```bash
cd /path/to/project
codex "$(cat .ccmigrate/handoffs/<timestamp>/codex-prompt.txt)"
```

Prefer `handoff` over native migration for very large sessions. Native migration preserves more raw history, but it can make Codex unusable when the transcript is huge.

## Native Claude Code to Codex Migration

Use native migration only when the user explicitly asks to run a Claude/Codex conversation in Codex.

The external `agent-migrator` repo is available at:

```text
/tmp/agent-migrator
```

List Claude Code sessions for a project:

```bash
uv run agent-migrator list --from claude-code --dir /Users/rajmeet/Dev/extract
```

Migrate a Claude Code session into Codex:

```bash
uv run agent-migrator move \
  --from claude-code \
  --to codex \
  --id <claude-session-id> \
  --dir /Users/rajmeet/Dev/extract
```

The command prints JSON containing `destination_id`. That is the new Codex session id.

Important Codex app behavior:

- A migrated session may not appear in the Codex app immediately.
- Run `codex resume <destination_id>` once from the project directory.
- After the CLI resumes it, the Codex app/session picker is more likely to show it.

Resume the migrated session:

```bash
cd /Users/rajmeet/Dev/extract
codex resume <destination_id>
```

If it is the newest Codex session for that project:

```bash
cd /Users/rajmeet/Dev/extract
codex resume --last
```

Verify Codex can see it:

```bash
uv run agent-migrator list --from codex --dir /Users/rajmeet/Dev/extract
find /Users/rajmeet/.codex/sessions -name '*<destination_id>*.jsonl' -print
```

## Clean-Room Constraint

`agent-migrator` is useful operationally, but its repository is licensed CC-BY-SA-4.0. Do not copy its implementation into this MIT project. Use it only as an external tool or architecture reference.

## Privacy

Conversation archives can include secrets, source code, customer data, and terminal output. Prefer `/tmp` for one-off exports and delete generated archives when done.
