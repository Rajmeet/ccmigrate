from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ccmigrate.archive import write_archive
from ccmigrate.exporters import export_markdown, export_transcript_jsonl
from ccmigrate.models import Conversation
from ccmigrate.util import write_json


def default_dump_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(f"ccmigrate-thread-dump-{stamp}")


def write_thread_dump(
    conversations: list[Conversation],
    out: Path,
    *,
    max_message_chars: int = 12000,
    make_zip: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    manifest = write_archive(out, conversations)
    markdown = export_markdown(conversations, out / "threads.md", max_message_chars)
    transcript_jsonl = export_transcript_jsonl(conversations, out / "threads.jsonl")
    readme = out / "README.md"
    readme.write_text(readme_text(conversations, note=note), encoding="utf-8")

    manifest["dump"] = {
        "readme": str(readme),
        "markdown": markdown,
        "transcript_jsonl": transcript_jsonl,
        "redaction_note": "Redaction is controlled by the CLI before dump writing.",
    }
    write_json(out / "manifest.json", manifest)

    if make_zip:
        zip_base = out.with_suffix("")
        zip_path = shutil.make_archive(str(zip_base), "zip", out)
        manifest["dump"]["zip"] = zip_path
        write_json(out / "manifest.json", manifest)
    return manifest


def readme_text(conversations: list[Conversation], *, note: str | None = None) -> str:
    providers = ", ".join(sorted({conv.provider for conv in conversations})) or "none"
    lines = [
        "# ccmigrate thread dump",
        "",
        "This bundle contains exported agent conversation threads.",
        "",
        "## Contents",
        "",
        "- `threads.md`: readable Markdown transcript",
        "- `threads.jsonl`: flattened typed transcript rows",
        "- `conversations.jsonl`: canonical ccmigrate archive",
        "- `manifest.json`: counts and file metadata",
        "",
        "## Inventory",
        "",
        f"- Conversations: {len(conversations)}",
        f"- Messages: {sum(len(conv.messages) for conv in conversations)}",
        f"- Tool calls: {sum(len(conv.tool_calls) for conv in conversations)}",
        f"- Providers: {providers}",
        "",
    ]
    if note:
        lines.extend(["## Note", "", note.strip(), ""])
    lines.extend(["## Threads", ""])
    for conv in conversations:
        lines.append(
            f"- `{conv.provider}` `{conv.updated_at or 'unknown'}` "
            f"`{conv.project or 'unknown'}` `{conv.id}` {conv.title or ''}".rstrip()
        )
    lines.extend(
        [
            "",
            "## Privacy",
            "",
            "Thread dumps can contain source code, terminal output, secrets, customer data, and private prompts.",
            "Use `ccmigrate dump` default redaction for external sharing, then inspect `threads.md` before sending.",
            "",
        ]
    )
    return "\n".join(lines)

