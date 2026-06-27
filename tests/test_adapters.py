from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ccmigrate.adapters import ClaudeAdapter, CodexAdapter, OpencodeAdapter
from ccmigrate.archive import load_archive, write_archive
from ccmigrate.dump import write_thread_dump
from ccmigrate.filters import filter_conversations
from ccmigrate.handoff import write_handoff
from ccmigrate.redaction import redact_conversations


class AdapterTests(unittest.TestCase):
    def test_claude_jsonl_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".claude" / "projects"
            project = root / "-tmp-demo"
            project.mkdir(parents=True)
            path = project / "session.jsonl"
            rows = [
                {"type": "user", "sessionId": "s1", "timestamp": "2026-01-01T00:00:00Z", "message": {"role": "user", "content": "build this"}},
                {"type": "assistant", "sessionId": "s1", "timestamp": "2026-01-01T00:00:01Z", "message": {"role": "assistant", "content": [{"type": "text", "text": "done"}]}},
                {
                    "type": "assistant",
                    "sessionId": "s1",
                    "timestamp": "2026-01-01T00:00:02Z",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "id": "toolu_1", "name": "Bash", "input": {"command": "pytest"}}],
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            conversations = ClaudeAdapter(root).conversations()

            self.assertEqual(len(conversations), 1)
            self.assertEqual(conversations[0].project, "/tmp/demo")
            self.assertEqual([message.role for message in conversations[0].messages], ["user", "assistant"])
            self.assertEqual(conversations[0].tool_calls[0].name, "Bash")

    def test_codex_jsonl_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex" / "sessions"
            root.mkdir(parents=True)
            path = root / "rollout.jsonl"
            rows = [
                {"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z", "payload": {"id": "c1", "cwd": "/repo", "model": "gpt"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:01Z", "payload": {"type": "user_message", "content": "fix bug"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:01Z", "payload": {"type": "function_call", "name": "shell_command", "arguments": "{\"command\":\"pytest\"}", "call_id": "call_1"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:01Z", "payload": {"type": "function_call_output", "call_id": "call_1", "output": "ok"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:02Z", "payload": {"type": "message", "content": [{"text": "fixed"}]}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            conversations = CodexAdapter(root).conversations()

            self.assertEqual(len(conversations), 1)
            self.assertEqual(conversations[0].project, "/repo")
            self.assertEqual([message.role for message in conversations[0].messages], ["user", "assistant"])
            self.assertEqual(conversations[0].tool_calls[0].name, "Bash")
            self.assertEqual(conversations[0].tool_calls[0].result, "ok")

    def test_opencode_storage_adapter_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "storage"
            session_id = "ses_1"
            message_id = "msg_1"
            (root / "session" / "global").mkdir(parents=True)
            (root / "message" / session_id).mkdir(parents=True)
            (root / "part" / message_id).mkdir(parents=True)
            (root / "session" / "global" / f"{session_id}.json").write_text(
                json.dumps({"id": session_id, "directory": "/repo", "title": "demo", "time": {"created": 1760000000000}}),
                encoding="utf-8",
            )
            (root / "message" / session_id / f"{message_id}.json").write_text(
                json.dumps({"id": message_id, "sessionID": session_id, "role": "user", "time": {"created": 1760000001000}}),
                encoding="utf-8",
            )
            (root / "part" / message_id / "part.json").write_text(
                json.dumps({"id": "part_1", "messageID": message_id, "type": "text", "text": "hello"}),
                encoding="utf-8",
            )

            conversations = OpencodeAdapter(root).conversations()
            store = Path(tmp) / "archive"
            write_archive(store, conversations)
            loaded = load_archive(store)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].messages[0].content, "hello")

    def test_filter_and_redact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex" / "sessions"
            root.mkdir(parents=True)
            path = root / "rollout.jsonl"
            rows = [
                {"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z", "payload": {"id": "c1", "cwd": "/repo/demo"}},
                {"type": "response_item", "timestamp": "2026-01-02T00:00:00Z", "payload": {"type": "user_message", "content": "token=ghp_abcdefghijklmnopqrstuvwxyz123456"}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            conversations = CodexAdapter(root).conversations()
            filtered = filter_conversations(conversations, project="demo", since="2026-01-01")
            redacted = redact_conversations(filtered)

            self.assertEqual(len(filtered), 1)
            self.assertIn("<redacted>", redacted[0].messages[0].content)

    def test_thread_dump_writes_shareable_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex" / "sessions"
            root.mkdir(parents=True)
            path = root / "rollout.jsonl"
            rows = [
                {"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z", "payload": {"id": "c1", "cwd": "/repo/demo"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:01Z", "payload": {"type": "user_message", "content": "share this"}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            conversations = CodexAdapter(root).conversations()
            out = Path(tmp) / "dump"
            manifest = write_thread_dump(conversations, out)

            self.assertEqual(manifest["conversation_count"], 1)
            self.assertTrue((out / "README.md").exists())
            self.assertTrue((out / "threads.md").exists())
            self.assertTrue((out / "threads.jsonl").exists())
            self.assertTrue((out / "conversations.jsonl").exists())

    def test_handoff_writes_compact_context_and_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".codex" / "sessions"
            root.mkdir(parents=True)
            path = root / "rollout.jsonl"
            rows = [
                {"type": "session_meta", "timestamp": "2026-01-01T00:00:00Z", "payload": {"id": "c1", "cwd": "/repo/demo"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:01Z", "payload": {"type": "user_message", "content": "continue this work"}},
                {"type": "response_item", "timestamp": "2026-01-01T00:00:02Z", "payload": {"type": "message", "role": "assistant", "content": [{"text": "next step is run tests"}]}},
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

            conversations = CodexAdapter(root).conversations()
            out = Path(tmp) / "handoff"
            manifest = write_handoff(conversations, out, include_dump=False)

            self.assertEqual(manifest["conversation_count"], 1)
            self.assertTrue((out / "HANDOFF.md").exists())
            self.assertTrue((out / "codex-prompt.txt").exists())
            self.assertIn("Next Steps", (out / "HANDOFF.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
