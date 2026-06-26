from __future__ import annotations

from datetime import datetime

from ccmigrate.models import Conversation


def filter_conversations(
    conversations: list[Conversation],
    *,
    project: str | None = None,
    since: str | None = None,
) -> list[Conversation]:
    result = conversations
    if project:
        needle = project.lower()
        result = [conv for conv in result if needle in (conv.project or "").lower()]
    if since:
        threshold = parse_datetime(since)
        result = [
            conv
            for conv in result
            if (parse_datetime(conv.updated_at) or parse_datetime(conv.created_at) or datetime.min)
            >= threshold
        ]
    return result


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(normalized + "T00:00:00")
        except ValueError as exc:
            raise ValueError(f"Invalid datetime: {value}") from exc
    if parsed.tzinfo is not None:
        return parsed.replace(tzinfo=None)
    return parsed

