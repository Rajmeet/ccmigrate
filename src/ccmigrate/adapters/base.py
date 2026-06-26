from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ccmigrate.filters import filter_conversations
from ccmigrate.models import Conversation, ConversationInfo, ProviderScan


class ProviderAdapter(ABC):
    name: str

    def __init__(self, root: Path):
        self.root = root.expanduser()

    @abstractmethod
    def scan(self) -> ProviderScan:
        raise NotImplementedError

    @abstractmethod
    def conversations(self, limit: int | None = None) -> list[Conversation]:
        raise NotImplementedError

    def list_conversations(
        self,
        *,
        limit: int | None = None,
        project: str | None = None,
        since: str | None = None,
    ) -> list[ConversationInfo]:
        load_limit = None if project or since else limit
        conversations = filter_conversations(
            self.conversations(limit=load_limit),
            project=project,
            since=since,
        )
        if limit is not None:
            conversations = conversations[:limit]
        return [conv.info() for conv in conversations]
