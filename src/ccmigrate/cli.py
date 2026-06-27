from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ccmigrate import __version__
from ccmigrate.adapters import ClaudeAdapter, CodexAdapter, OpencodeAdapter
from ccmigrate.adapters.base import ProviderAdapter
from ccmigrate.archive import load_archive, write_archive
from ccmigrate.dump import default_dump_dir, write_thread_dump
from ccmigrate.exporters import export_all, export_markdown, export_transcript_jsonl, provider_memory_files
from ccmigrate.filters import filter_conversations
from ccmigrate.handoff import default_handoff_dir, write_handoff
from ccmigrate.models import Conversation
from ccmigrate.redaction import redact_conversations

ADAPTERS = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "opencode": OpencodeAdapter,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ccmigrate",
        description="Sync local agent chats into a portable cross-provider archive.",
    )
    parser.add_argument("--version", action="version", version=f"ccmigrate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    for command in ("doctor", "scan", "list", "sync", "dump", "handoff"):
        command_parser = sub.add_parser(command)
        add_common_args(command_parser)
        if command == "scan":
            command_parser.add_argument("--json", action="store_true", help="Print machine-readable scan output.")
            command_parser.set_defaults(func=cmd_scan)
        elif command == "list":
            command_parser.add_argument("--json", action="store_true", help="Print machine-readable conversation output.")
            command_parser.add_argument("--limit", type=int, help="Maximum conversations per provider.")
            command_parser.set_defaults(func=cmd_list)
        elif command == "sync":
            command_parser.add_argument("--limit", type=int, help="Maximum conversations per provider.")
            command_parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing an archive.")
            command_parser.add_argument("--redact", action="store_true", help="Redact common secrets before writing.")
            command_parser.set_defaults(func=cmd_sync)
        elif command == "dump":
            command_parser.add_argument("--id", action="append", dest="conversation_ids", help="Conversation id to dump. Repeatable.")
            command_parser.add_argument("--all", action="store_true", help="Allow dumping every matching provider conversation.")
            command_parser.add_argument("--limit", type=int, help="Maximum conversations to dump after filtering. Default: 1 unless --all is set.")
            command_parser.add_argument("--out", type=Path, default=None, help="Output directory. Default: timestamped dump directory.")
            command_parser.add_argument("--zip", action="store_true", help="Also create a .zip next to the output directory.")
            command_parser.add_argument("--no-redact", action="store_true", help="Disable default secret redaction.")
            command_parser.add_argument("--max-message-chars", type=int, default=12000, help="Markdown truncation limit per message.")
            command_parser.add_argument("--note", help="Optional note to include in the dump README.")
            command_parser.set_defaults(func=cmd_dump)
        elif command == "handoff":
            command_parser.add_argument("--id", action="append", dest="conversation_ids", help="Conversation id to hand off. Repeatable; first match is used.")
            command_parser.add_argument("--limit", type=int, default=1, help="Maximum conversations to inspect after filtering. Default: 1.")
            command_parser.add_argument("--out", type=Path, default=None, help="Output directory. Default: <project>/.ccmigrate/handoffs/<timestamp> when --project is a path.")
            command_parser.add_argument("--recent-messages", type=int, default=24, help="Number of recent messages to include.")
            command_parser.add_argument("--max-chars", type=int, default=24000, help="Approximate character budget for HANDOFF.md.")
            command_parser.add_argument("--no-dump", action="store_true", help="Do not include the full dump next to the handoff.")
            command_parser.add_argument("--no-shards", action="store_true", help="Do not split the transcript into searchable shard files.")
            command_parser.add_argument("--shard-chars", type=int, default=50000, help="Approximate character budget per searchable shard.")
            command_parser.add_argument("--zip", action="store_true", help="Zip the optional full dump.")
            command_parser.add_argument("--no-redact", action="store_true", help="Disable default secret redaction.")
            command_parser.add_argument("--note", help="Optional note to include in the handoff.")
            command_parser.set_defaults(func=cmd_handoff)
        else:
            command_parser.set_defaults(func=cmd_doctor)

    export = sub.add_parser("export")
    export.add_argument("--store", type=Path, default=Path(".ccmigrate"), help="Archive directory.")
    export.add_argument("--out", type=Path, default=Path(".ccmigrate/export"), help="Export directory.")
    export.add_argument(
        "--format",
        choices=("all", "markdown", "jsonl", "provider-memory"),
        default="all",
        help="Export format.",
    )
    export.add_argument("--max-message-chars", type=int, default=8000, help="Markdown truncation limit per message.")
    export.add_argument("--project", help="Only export conversations whose project path contains this text.")
    export.add_argument("--since", help="Only export conversations updated on or after this ISO date/datetime.")
    export.add_argument("--redact", action="store_true", help="Redact common secrets in generated exports.")
    export.set_defaults(func=cmd_export)
    return parser


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--home", type=Path, default=Path.home(), help="Home directory used for default provider paths.")
    parser.add_argument("--store", type=Path, default=Path(".ccmigrate"), help="Archive directory.")
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=tuple(ADAPTERS),
        default=list(ADAPTERS),
        help="Providers to include.",
    )
    parser.add_argument("--claude-root", type=Path, help="Claude Code projects root.")
    parser.add_argument("--codex-root", type=Path, help="Codex sessions root.")
    parser.add_argument("--opencode-root", type=Path, help="opencode storage root.")
    parser.add_argument("--project", help="Only include conversations whose project path contains this text.")
    parser.add_argument("--since", help="Only include conversations updated on or after this ISO date/datetime.")


def cmd_doctor(args: argparse.Namespace) -> int:
    scans = [adapter.scan() for adapter in make_adapters(args)]
    print(f"ccmigrate {__version__}")
    for scan in scans:
        status = "ok" if scan.exists else "missing"
        note = f" ({scan.note})" if scan.note else ""
        print(f"{scan.provider:8} {status:7} {scan.conversation_count:6} conversations  {scan.root}{note}")
    return 0 if any(scan.exists for scan in scans) else 1


def cmd_scan(args: argparse.Namespace) -> int:
    scans = [adapter.scan() for adapter in make_adapters(args)]
    if args.json:
        print(json.dumps([scan.to_dict() for scan in scans], indent=2))
    else:
        for scan in scans:
            status = "ok" if scan.exists else "missing"
            print(f"{scan.provider:8} {status:7} {scan.conversation_count:6} {scan.root}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    infos = []
    for adapter in make_adapters(args):
        infos.extend(adapter.list_conversations(limit=args.limit, project=args.project, since=args.since))
    infos.sort(key=lambda info: info.updated_at or info.created_at or "", reverse=True)
    if args.json:
        print(json.dumps([info.to_dict() for info in infos], indent=2))
    else:
        for info in infos:
            title = (info.title or info.id)[:72]
            print(
                f"{info.provider:8} {info.updated_at or 'unknown':28} "
                f"{info.message_count:5} msgs {info.tool_call_count:4} tools  "
                f"{info.project or 'unknown'}  {title}"
            )
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    conversations = load_provider_conversations(args, limit=args.limit)
    if args.redact:
        conversations = redact_conversations(conversations)
    if args.dry_run:
        print_summary(conversations, label="Would sync")
        return 0
    manifest = write_archive(args.store, conversations)
    print(
        "Synced "
        f"{manifest['conversation_count']} conversations, {manifest['message_count']} messages, "
        f"and {manifest['tool_call_count']} tool calls "
        f"to {manifest['archive']}"
    )
    return 0


def cmd_dump(args: argparse.Namespace) -> int:
    if not (args.all or args.project or args.since or args.conversation_ids):
        print(
            "Refusing to dump without a selector. Use --project, --since, --id, or explicit --all.",
            file=sys.stderr,
        )
        return 2

    dump_limit = args.limit
    if dump_limit is None and not args.all and not args.conversation_ids:
        dump_limit = 1

    conversations = load_provider_conversations(args, limit=None if args.conversation_ids else dump_limit)
    if args.conversation_ids:
        wanted = set(args.conversation_ids)
        conversations = [conv for conv in conversations if conv.id in wanted or (conv.metadata.get("session_id") in wanted)]
    if dump_limit is not None and not args.conversation_ids:
        conversations = conversations[:dump_limit]
    if not conversations:
        print("No conversations matched the dump selectors.", file=sys.stderr)
        return 1

    redacted = not args.no_redact
    if redacted:
        conversations = redact_conversations(conversations)

    out = args.out or default_dump_dir()
    manifest = write_thread_dump(
        conversations,
        out,
        max_message_chars=args.max_message_chars,
        make_zip=args.zip,
        note=args.note,
    )
    print(
        f"Dumped {manifest['conversation_count']} conversations, "
        f"{manifest['message_count']} messages, and {manifest['tool_call_count']} tool calls to {out}"
    )
    if redacted:
        print("Redaction: enabled. Use --no-redact only for trusted/private sharing.")
    zip_path = manifest.get("dump", {}).get("zip")
    if zip_path:
        print(f"zip: {zip_path}")
    print(f"markdown: {out / 'threads.md'}")
    print(f"jsonl: {out / 'threads.jsonl'}")
    return 0


def cmd_handoff(args: argparse.Namespace) -> int:
    if not (args.project or args.since or args.conversation_ids):
        print("Refusing to create a handoff without --project, --since, or --id.", file=sys.stderr)
        return 2

    conversations = load_provider_conversations(args, limit=None if args.conversation_ids else args.limit)
    if args.conversation_ids:
        wanted = set(args.conversation_ids)
        conversations = [conv for conv in conversations if conv.id in wanted or (conv.metadata.get("session_id") in wanted)]
    if not conversations:
        print("No conversations matched the handoff selectors.", file=sys.stderr)
        return 1
    conversations = conversations[:1]

    redacted = not args.no_redact
    if redacted:
        conversations = redact_conversations(conversations)

    out = args.out or default_handoff_dir(project=args.project if args.project and Path(args.project).is_absolute() else conversations[0].project)
    manifest = write_handoff(
        conversations,
        out,
        recent_messages=args.recent_messages,
        max_chars=args.max_chars,
        include_dump=not args.no_dump,
        make_zip=args.zip,
        include_shards=not args.no_shards,
        shard_chars=args.shard_chars,
        note=args.note,
    )
    print(
        f"Wrote compact handoff for 1 conversation, "
        f"{manifest['message_count']} messages, and {manifest['tool_call_count']} tool calls to {out}"
    )
    if redacted:
        print("Redaction: enabled. Use --no-redact only for trusted/private local continuation.")
    print(f"handoff: {manifest['handoff']}")
    print(f"prompt: {manifest['codex_prompt']}")
    shards = manifest.get("search_shards", {})
    if shards:
        print(f"search_shards: {shards.get('directory')} ({shards.get('file_count')} files)")
    print()
    print("Start fresh Codex with:")
    print(f"  cd {conversations[0].project or Path.cwd()}")
    print(f"  codex \"$(cat {manifest['codex_prompt']})\"")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    conversations = load_archive(args.store)
    if not conversations:
        print(f"No archive found at {args.store / 'conversations.jsonl'}", file=sys.stderr)
        return 1
    conversations = filter_conversations(conversations, project=args.project, since=args.since)
    if args.redact:
        conversations = redact_conversations(conversations)

    args.out.mkdir(parents=True, exist_ok=True)
    if args.format == "all":
        paths = export_all(conversations, args.out, args.max_message_chars)
    elif args.format == "markdown":
        paths = {"markdown": export_markdown(conversations, args.out / "conversations.md", args.max_message_chars)}
    elif args.format == "jsonl":
        paths = {"jsonl": export_transcript_jsonl(conversations, args.out / "conversations.jsonl")}
    else:
        paths = {}
        for name, content in provider_memory_files(conversations).items():
            path = args.out / name
            path.write_text(content, encoding="utf-8")
            paths[name] = str(path)

    for kind, path in paths.items():
        print(f"{kind}: {path}")
    return 0


def make_adapters(args: argparse.Namespace) -> list[ProviderAdapter]:
    roots = {
        "claude": args.claude_root or args.home / ".claude" / "projects",
        "codex": args.codex_root or args.home / ".codex" / "sessions",
        "opencode": args.opencode_root or args.home / ".local" / "share" / "opencode" / "storage",
    }
    return [ADAPTERS[name](roots[name]) for name in args.providers]


def load_provider_conversations(args: argparse.Namespace, *, limit: int | None) -> list[Conversation]:
    conversations: list[Conversation] = []
    load_limit = None if args.project or args.since else limit
    for adapter in make_adapters(args):
        conversations.extend(adapter.conversations(limit=load_limit))
    conversations = filter_conversations(conversations, project=args.project, since=args.since)
    conversations.sort(key=lambda conv: conv.updated_at or conv.created_at or "", reverse=True)
    if load_limit is None and limit is not None:
        conversations = conversations[:limit]
    return conversations


def print_summary(conversations: list[Conversation], *, label: str) -> None:
    providers = sorted({conv.provider for conv in conversations})
    print(
        f"{label} {len(conversations)} conversations, "
        f"{sum(len(conv.messages) for conv in conversations)} messages, "
        f"{sum(len(conv.tool_calls) for conv in conversations)} tool calls "
        f"from {', '.join(providers) or 'no providers'}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
