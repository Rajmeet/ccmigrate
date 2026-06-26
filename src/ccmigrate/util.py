from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

PLAN_RE = re.compile(r"<proposed_plan>(.*?)</proposed_plan>", re.DOTALL | re.IGNORECASE)


def stable_id(*parts: object) -> str:
    raw = "\x1f".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                yield {
                    "_ccmigrate_error": "json_decode",
                    "line": line_number,
                    "message": str(exc),
                }
                continue
            if isinstance(obj, dict):
                yield obj


def read_json(path: Path) -> Any | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
            count += 1
    return count


def coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            text = extract_text(item)
            if text:
                parts.append(text)
        return "\n".join(parts)
    if isinstance(value, dict):
        return extract_text(value)
    return str(value)


def extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return coerce_text(value)
    if not isinstance(value, dict):
        return ""

    direct_keys = ("text", "content", "summary", "message", "input", "output")
    for key in direct_keys:
        text = value.get(key)
        if isinstance(text, str) and text.strip():
            return text

    nested_keys = ("content", "parts", "delta", "item", "state")
    for key in nested_keys:
        if key in value:
            text = coerce_text(value[key])
            if text.strip():
                return text
    return ""


def extract_plan(value: str) -> str | None:
    match = PLAN_RE.search(value)
    if not match:
        return None
    plan = match.group(1).strip()
    return plan or None


def first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value:
            return value
    return None


def utcish_from_millis(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        from datetime import datetime, timezone

        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    return None


def project_from_claude_dir(name: str) -> str:
    if not name.startswith("-"):
        return name
    return "/" + name[1:].replace("-", "/")
