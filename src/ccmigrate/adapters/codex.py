from __future__ import annotations

from pathlib import Path
from typing import Any

from ccmigrate.adapters.base import ProviderAdapter
from ccmigrate.models import Conversation, Message, ProviderScan, StandardToolName, ToolCall
from ccmigrate.util import extract_plan, extract_text, first_string, read_jsonl, stable_id


class CodexAdapter(ProviderAdapter):
    name = "codex"

    def scan(self) -> ProviderScan:
        if not self.root.exists():
            return ProviderScan(self.name, str(self.root), False, 0, "root not found")
        count = sum(1 for _ in self._files())
        return ProviderScan(self.name, str(self.root), True, count)

    def conversations(self, limit: int | None = None) -> list[Conversation]:
        index = self._session_index()
        conversations: list[Conversation] = []
        for path in self._files():
            conv = self._parse_file(path, index)
            if conv.messages:
                conversations.append(conv)
            if limit is not None and len(conversations) >= limit:
                break
        return conversations

    def _files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return sorted(self.root.glob("**/*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)

    def _session_index(self) -> dict[str, dict[str, Any]]:
        index_path = self.root.parent / "session_index.jsonl"
        rows: dict[str, dict[str, Any]] = {}
        if not index_path.exists():
            return rows
        for row in read_jsonl(index_path):
            session_id = row.get("id")
            if isinstance(session_id, str):
                rows[session_id] = row
        return rows

    def _parse_file(self, path: Path, index: dict[str, dict[str, Any]]) -> Conversation:
        messages: list[Message] = []
        tool_calls: list[ToolCall] = []
        tool_by_call_id: dict[str, ToolCall] = {}
        session_id: str | None = None
        project: str | None = None
        model: str | None = None
        created_at: str | None = None
        updated_at: str | None = None
        plan_content: str | None = None

        for row in read_jsonl(path):
            payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
            timestamp = first_string(row.get("timestamp"), payload.get("timestamp"))
            if timestamp:
                created_at = created_at or timestamp
                updated_at = timestamp

            if row.get("type") == "session_meta":
                session_id = first_string(session_id, payload.get("id"))
                project = first_string(project, payload.get("cwd"))
                model = first_string(model, payload.get("model"), payload.get("model_provider"))
                continue

            if row.get("type") == "turn_context":
                project = first_string(project, payload.get("cwd"))
                model = first_string(model, payload.get("model"))

            tool_call = extract_tool_call(payload, timestamp)
            if tool_call:
                tool_calls.append(tool_call)
                call_id = tool_call.id
                if call_id:
                    tool_by_call_id[call_id] = tool_call
                continue

            call_output = extract_tool_output(payload)
            if call_output:
                call_id, output = call_output
                if call_id in tool_by_call_id:
                    tool_by_call_id[call_id].result = output
                continue

            role = first_string(payload.get("role"), payload.get("author"), infer_role(payload))
            content = extract_text(payload)
            if not content.strip():
                continue
            plan_content = plan_content or extract_plan(content)

            messages.append(
                Message(
                    id=first_string(payload.get("id"), payload.get("item_id"), row.get("id")),
                    role=normalize_role(role or "other"),
                    content=content,
                    created_at=timestamp,
                    metadata={
                        "provider_type": row.get("type"),
                        "payload_type": payload.get("type"),
                        "encrypted": "encrypted_content" in payload,
                    },
                )
            )

        fallback_id = session_id or path.stem
        indexed = index.get(fallback_id, {})
        title = first_string(indexed.get("thread_name"), path.stem)
        return Conversation(
            id=stable_id(self.name, fallback_id, str(path)),
            provider=self.name,
            source_path=str(path),
            project=project,
            title=title,
            created_at=created_at,
            updated_at=updated_at or first_string(indexed.get("updated_at")),
            messages=messages,
            tool_calls=tool_calls,
            plan_content=plan_content,
            metadata={"session_id": session_id, "model": model},
        )


def infer_role(payload: dict[str, Any]) -> str | None:
    payload_type = payload.get("type")
    if payload_type in {"message", "assistant_message"}:
        return "assistant"
    if payload_type in {"user_message", "input_text"}:
        return "user"
    return None


def normalize_role(role: str) -> str:
    role = role.lower()
    if role in {"user", "assistant", "system", "tool"}:
        return role
    if role in {"agent", "model"}:
        return "assistant"
    return "other"


def extract_tool_call(payload: dict[str, Any], timestamp: str | None) -> ToolCall | None:
    payload_type = payload.get("type")
    if payload_type not in {"function_call", "custom_tool_call"}:
        return None
    native_name = first_string(payload.get("name"), "unknown") or "unknown"
    call_id = first_string(payload.get("call_id"), payload.get("id"))
    input_payload = payload.get("input")
    if input_payload is None:
        input_payload = payload.get("arguments")
    return ToolCall(
        id=call_id,
        name=standard_tool_name(native_name),
        input=normalize_tool_input(input_payload),
        result=None,
        created_at=timestamp,
        metadata={"native_name": native_name, "payload_type": payload_type},
    )


def extract_tool_output(payload: dict[str, Any]) -> tuple[str, str] | None:
    if payload.get("type") not in {"function_call_output", "custom_tool_call_output"}:
        return None
    call_id = first_string(payload.get("call_id"), payload.get("id"))
    if not call_id:
        return None
    return call_id, extract_text(payload.get("output")) or extract_text(payload)


def normalize_tool_input(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"raw": value}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {}


def standard_tool_name(native_name: str) -> str:
    mapping = {
        "shell_command": StandardToolName.BASH,
        "shell": StandardToolName.BASH,
        "apply_patch": StandardToolName.EDIT,
        "file_read": StandardToolName.READ,
        "file_write": StandardToolName.WRITE,
        "file_edit": StandardToolName.EDIT,
    }
    return mapping.get(native_name, native_name)
