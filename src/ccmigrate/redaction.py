from __future__ import annotations

import copy
import re

from ccmigrate.models import Conversation

SECRET_PATTERNS = [
    re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"),
    re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]{20,})\b"),
    re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*['\"]?([^'\"\s]{8,})"
    ),
]


def redact_conversations(conversations: list[Conversation]) -> list[Conversation]:
    redacted = copy.deepcopy(conversations)
    for conv in redacted:
        for message in conv.messages:
            message.content = redact_text(message.content)
        for tool_call in conv.tool_calls:
            if tool_call.result:
                tool_call.result = redact_text(tool_call.result)
            tool_call.input = redact_obj(tool_call.input)
        if conv.plan_content:
            conv.plan_content = redact_text(conv.plan_content)
    return redacted


def redact_obj(value):
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_obj(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_obj(item) for key, item in value.items()}
    return value


def redact_text(value: str) -> str:
    result = value
    for pattern in SECRET_PATTERNS:
        result = pattern.sub(lambda match: redact_match(match), result)
    return result


def redact_match(match: re.Match[str]) -> str:
    if match.lastindex and match.lastindex >= 2:
        return f"{match.group(1)}=<redacted>"
    return "<redacted>"

