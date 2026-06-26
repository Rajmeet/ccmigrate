from __future__ import annotations

from pathlib import Path

from ccmigrate.adapters.base import ProviderAdapter
from typing import Any

from ccmigrate.models import Conversation, Message, ProviderScan, StandardToolName, ToolCall
from ccmigrate.util import extract_plan, extract_text, first_string, project_from_claude_dir, read_jsonl, stable_id


class ClaudeAdapter(ProviderAdapter):
    name = "claude"

    def scan(self) -> ProviderScan:
        if not self.root.exists():
            return ProviderScan(self.name, str(self.root), False, 0, "root not found")
        count = sum(1 for _ in self._files())
        return ProviderScan(self.name, str(self.root), True, count)

    def conversations(self, limit: int | None = None) -> list[Conversation]:
        conversations: list[Conversation] = []
        for path in self._files():
            conv = self._parse_file(path)
            if conv.messages:
                conversations.append(conv)
            if limit is not None and len(conversations) >= limit:
                break
        return conversations

    def _files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(
            (
                path
                for path in self.root.glob("**/*.jsonl")
                if "tool-results" not in path.parts and path.name != "sessions-index.json"
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def _parse_file(self, path: Path) -> Conversation:
        messages: list[Message] = []
        tool_calls: list[ToolCall] = []
        session_id: str | None = None
        created_at: str | None = None
        updated_at: str | None = None
        title: str | None = None
        plan_content: str | None = None

        for row in read_jsonl(path):
            session_id = first_string(session_id, row.get("sessionId"), row.get("session_id"))
            timestamp = first_string(row.get("timestamp"), row.get("createdAt"), row.get("updatedAt"))
            if timestamp:
                created_at = created_at or timestamp
                updated_at = timestamp

            message_obj = row.get("message") if isinstance(row.get("message"), dict) else {}
            tool_calls.extend(extract_tool_calls(row, message_obj, timestamp))
            role = first_string(
                message_obj.get("role"),
                row.get("role"),
                row.get("type") if row.get("type") in {"user", "assistant", "system"} else None,
            )
            content = extract_text(message_obj) or extract_text(row.get("content")) or extract_text(row)
            if not role or not content.strip():
                if row.get("type") == "summary":
                    title = title or content[:120]
                continue
            plan_content = plan_content or extract_plan(content)

            messages.append(
                Message(
                    id=first_string(row.get("uuid"), row.get("id"), message_obj.get("id")),
                    role=normalize_role(role),
                    content=content,
                    created_at=timestamp,
                    metadata={"provider_type": row.get("type"), "parent_uuid": row.get("parentUuid")},
                )
            )

        project = project_from_path(self.root, path)
        conv_id = stable_id(self.name, session_id or path.stem, str(path))
        return Conversation(
            id=conv_id,
            provider=self.name,
            source_path=str(path),
            project=project,
            title=title or path.stem,
            created_at=created_at,
            updated_at=updated_at,
            messages=messages,
            tool_calls=tool_calls,
            plan_content=plan_content,
            metadata={"session_id": session_id, "is_subagent": "subagents" in path.parts},
        )


def normalize_role(role: str) -> str:
    role = role.lower()
    if role in {"human"}:
        return "user"
    if role in {"ai", "bot"}:
        return "assistant"
    if role in {"user", "assistant", "system", "tool"}:
        return role
    return "other"


def extract_tool_calls(row: dict[str, Any], message_obj: dict[str, Any], timestamp: str | None) -> list[ToolCall]:
    content = message_obj.get("content")
    if not isinstance(content, list):
        return []
    calls: list[ToolCall] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            native_name = first_string(block.get("name"), "unknown") or "unknown"
            calls.append(
                ToolCall(
                    id=first_string(block.get("id")),
                    name=standard_tool_name(native_name),
                    input=block.get("input") if isinstance(block.get("input"), dict) else {},
                    result=None,
                    created_at=timestamp,
                    metadata={
                        "native_name": native_name,
                        "provider_type": row.get("type"),
                    },
                )
            )
    return calls


def standard_tool_name(native_name: str) -> str:
    mapping = {
        "Read": StandardToolName.READ,
        "Write": StandardToolName.WRITE,
        "Edit": StandardToolName.EDIT,
        "MultiEdit": StandardToolName.MULTI_EDIT,
        "Bash": StandardToolName.BASH,
        "Glob": StandardToolName.GLOB,
        "Grep": StandardToolName.GREP,
        "WebFetch": StandardToolName.WEB_FETCH,
        "WebSearch": StandardToolName.WEB_SEARCH,
        "TodoWrite": StandardToolName.TODO_WRITE,
        "TodoRead": StandardToolName.TODO_READ,
        "ExitPlanMode": StandardToolName.PLAN,
        "ExitPlanModeV2": StandardToolName.PLAN,
    }
    return mapping.get(native_name, native_name)


def project_from_path(root: Path, path: Path) -> str | None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return project_from_claude_dir(relative.parts[0])
