# Contributing

Thanks for helping improve `ccmigrate`.

## Development

```bash
python3 -m pip install -e .
python3 -m unittest
```

## Adapter rules

- Provider adapters must be read-only.
- Extract text messages, tool calls, and plan content into the canonical schema where possible.
- Keep provider-specific raw metadata under `metadata`; keep the canonical schema stable.
- Map common tools to `StandardToolName` values instead of preserving provider-only names when there is a clear equivalent.
- Prefer tolerant parsing over hard failures.
- Do not add network calls to sync/export paths.
- Do not write into provider-owned history stores without a separate explicit command and clear backup behavior.
- If native import/write support is added later, it must use backups, atomic writes, explicit opt-in flags, and rollback/delete tests.

## Privacy

Chat archives can contain secrets, source code, credentials, and personal data. Avoid adding telemetry, remote uploads, or crash reporting. New features should keep local data local by default.
