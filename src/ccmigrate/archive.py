from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ccmigrate.models import SCHEMA_VERSION, Conversation, Message, ToolCall
from ccmigrate.util import write_json, write_jsonl


def write_archive(store: Path, conversations: list[Conversation]) -> dict[str, Any]:
    store.mkdir(parents=True, exist_ok=True)
    archive_path = store / "conversations.jsonl"
    count = write_jsonl(archive_path, (conv.to_dict() for conv in conversations))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "conversation_count": count,
        "message_count": sum(len(conv.messages) for conv in conversations),
        "tool_call_count": sum(len(conv.tool_calls) for conv in conversations),
        "turn_count": sum(conv.turn_count for conv in conversations),
        "providers": sorted({conv.provider for conv in conversations}),
        "archive": str(archive_path),
    }
    write_json(store / "manifest.json", manifest)
    return manifest


def load_archive(store: Path) -> list[Conversation]:
    archive_path = store / "conversations.jsonl"
    conversations: list[Conversation] = []
    if not archive_path.exists():
        return conversations
    with archive_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            messages = [
                Message(
                    id=message.get("id"),
                    role=message.get("role", "other"),
                    content=message.get("content", ""),
                    created_at=message.get("created_at"),
                    metadata=message.get("metadata") or {},
                )
                for message in payload.get("messages", [])
                if isinstance(message, dict)
            ]
            tool_calls = [
                ToolCall(
                    id=tool_call.get("id"),
                    name=tool_call.get("name", "unknown"),
                    input=tool_call.get("input") or {},
                    result=tool_call.get("result"),
                    created_at=tool_call.get("created_at"),
                    metadata=tool_call.get("metadata") or {},
                )
                for tool_call in payload.get("tool_calls", [])
                if isinstance(tool_call, dict)
            ]
            conversations.append(
                Conversation(
                    id=payload["id"],
                    provider=payload["provider"],
                    source_path=payload["source_path"],
                    project=payload.get("project"),
                    title=payload.get("title"),
                    created_at=payload.get("created_at"),
                    updated_at=payload.get("updated_at"),
                    messages=messages,
                    tool_calls=tool_calls,
                    plan_content=payload.get("plan_content"),
                    metadata=payload.get("metadata") or {},
                )
            )
    return conversations
