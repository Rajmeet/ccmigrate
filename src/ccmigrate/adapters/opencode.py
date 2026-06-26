from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ccmigrate.adapters.base import ProviderAdapter
from ccmigrate.models import Conversation, Message, ProviderScan, ToolCall
from ccmigrate.util import extract_plan, extract_text, first_string, read_json, stable_id, utcish_from_millis


class OpencodeAdapter(ProviderAdapter):
    name = "opencode"

    def scan(self) -> ProviderScan:
        session_root = self.root / "session"
        if not session_root.exists():
            return ProviderScan(self.name, str(self.root), False, 0, "session root not found")
        count = sum(1 for _ in session_root.glob("**/*.json"))
        return ProviderScan(self.name, str(self.root), True, count)

    def conversations(self, limit: int | None = None) -> list[Conversation]:
        conversations: list[Conversation] = []
        parts_by_message = self._parts_by_message()
        for path in self._session_files():
            session = read_json(path)
            if not isinstance(session, dict):
                continue
            conv = self._parse_session(path, session, parts_by_message)
            if conv.messages:
                conversations.append(conv)
            if limit is not None and len(conversations) >= limit:
                break
        return conversations

    def _session_files(self) -> list[Path]:
        session_root = self.root / "session"
        if not session_root.exists():
            return []
        return sorted(session_root.glob("**/*.json"), key=lambda path: path.stat().st_mtime, reverse=True)

    def _message_files(self, session_id: str) -> list[Path]:
        return sorted((self.root / "message" / session_id).glob("*.json"), key=lambda path: path.stat().st_mtime)

    def _parts_by_message(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        part_root = self.root / "part"
        if not part_root.exists():
            return grouped
        for path in sorted(part_root.glob("*/*.json"), key=lambda item: item.stat().st_mtime):
            part = read_json(path)
            if not isinstance(part, dict):
                continue
            message_id = part.get("messageID")
            if isinstance(message_id, str):
                grouped[message_id].append(part)
        return grouped

    def _parse_session(
        self,
        path: Path,
        session: dict[str, Any],
        parts_by_message: dict[str, list[dict[str, Any]]],
    ) -> Conversation:
        session_id = first_string(session.get("id"), path.stem)
        messages: list[Message] = []
        tool_calls: list[ToolCall] = []
        plan_content: str | None = None
        created_at = time_value(session.get("time"), "created")
        updated_at = time_value(session.get("time"), "updated")

        for message_path in self._message_files(session_id or path.stem):
            raw_message = read_json(message_path)
            if not isinstance(raw_message, dict):
                continue
            message_id = first_string(raw_message.get("id"), message_path.stem)
            role = normalize_role(first_string(raw_message.get("role"), "other") or "other")
            timestamp = time_value(raw_message.get("time"), "created")
            parts = parts_by_message.get(message_id or "", [])
            content_parts: list[str] = []
            for part in parts:
                if is_tool_part(part):
                    tool_calls.append(tool_call_from_part(part, timestamp))
                else:
                    text = extract_text(part)
                    if text:
                        content_parts.append(text)
            content = "\n".join(content_parts)
            if not content.strip():
                content = extract_text(raw_message)
            if not content.strip():
                continue
            plan_content = plan_content or extract_plan(content)
            messages.append(
                Message(
                    id=message_id,
                    role=role,
                    content=content,
                    created_at=timestamp,
                    metadata={
                        "model": raw_message.get("modelID"),
                        "provider_id": raw_message.get("providerID"),
                        "agent": raw_message.get("agent"),
                        "part_count": len(parts),
                    },
                )
            )

        messages.sort(key=lambda msg: msg.created_at or "")
        tool_calls.sort(key=lambda call: call.created_at or "")
        return Conversation(
            id=stable_id(self.name, session_id, str(path)),
            provider=self.name,
            source_path=str(path),
            project=first_string(session.get("directory"), session.get("projectID")),
            title=first_string(session.get("title"), session.get("slug"), path.stem),
            created_at=created_at,
            updated_at=updated_at,
            messages=messages,
            tool_calls=tool_calls,
            plan_content=plan_content,
            metadata={
                "session_id": session_id,
                "version": session.get("version"),
                "summary": session.get("summary"),
            },
        )


def normalize_role(role: str) -> str:
    role = role.lower()
    if role in {"user", "assistant", "system", "tool"}:
        return role
    return "other"


def is_tool_part(part: dict[str, Any]) -> bool:
    return bool(part.get("tool") or part.get("callID") or part.get("type") in {"tool", "tool_call"})


def tool_call_from_part(part: dict[str, Any], timestamp: str | None) -> ToolCall:
    state = part.get("state") if isinstance(part.get("state"), dict) else {}
    return ToolCall(
        id=first_string(part.get("callID"), part.get("id")),
        name=first_string(part.get("tool"), part.get("type"), "unknown") or "unknown",
        input=state.get("input") if isinstance(state.get("input"), dict) else {},
        result=extract_text(state.get("output")) or extract_text(state.get("result")) or None,
        created_at=timestamp,
        metadata={
            "part_id": part.get("id"),
            "message_id": part.get("messageID"),
            "state": state,
        },
    )


def time_value(value: Any, key: str) -> str | None:
    if isinstance(value, dict):
        return utcish_from_millis(value.get(key)) or utcish_from_millis(value.get(key + "At"))
    return utcish_from_millis(value)
