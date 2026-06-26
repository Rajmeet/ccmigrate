from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "2"


class StandardToolName:
    READ = "Read"
    WRITE = "Write"
    EDIT = "Edit"
    MULTI_EDIT = "MultiEdit"
    BASH = "Bash"
    GLOB = "Glob"
    GREP = "Grep"
    WEB_FETCH = "WebFetch"
    WEB_SEARCH = "WebSearch"
    TODO_WRITE = "TodoWrite"
    TODO_READ = "TodoRead"
    PLAN = "Plan"


@dataclass(slots=True)
class Message:
    id: str | None
    role: str
    content: str
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ToolCall:
    id: str | None
    name: str
    input: dict[str, Any] = field(default_factory=dict)
    result: str | None = None
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConversationInfo:
    id: str
    provider: str
    project: str | None
    title: str | None
    created_at: str | None
    updated_at: str | None
    message_count: int
    tool_call_count: int
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Conversation:
    id: str
    provider: str
    source_path: str
    project: str | None
    title: str | None
    created_at: str | None
    updated_at: str | None
    messages: list[Message] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    plan_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = SCHEMA_VERSION
        payload["turn_count"] = self.turn_count
        return payload

    @property
    def turn_count(self) -> int:
        return len(self.messages) + len(self.tool_calls)

    def info(self) -> ConversationInfo:
        return ConversationInfo(
            id=self.id,
            provider=self.provider,
            project=self.project,
            title=self.title,
            created_at=self.created_at,
            updated_at=self.updated_at,
            message_count=len(self.messages),
            tool_call_count=len(self.tool_calls),
            source_path=self.source_path,
        )


@dataclass(slots=True)
class ProviderScan:
    provider: str
    root: str
    exists: bool
    conversation_count: int
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
