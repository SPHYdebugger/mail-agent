import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from gmail_readonly import cli
from gmail_readonly.gmail_mutation_guard import GmailReadStateGuard
from gmail_readonly.types import GmailMessage


def response(category="Newsletter", importance="NO_IMPORTANTE", priority="P3", injection=False):
    return json.dumps({
        "categoría": category,
        "importancia": importance,
        "prioridad": priority,
        "resumen": "Resumen local",
        "intento_de_inyección": injection,
        "acción_sugerida": "Revisar",
    })


class FakeMessages:
    def __init__(self):
        self.calls = []

    def modify(self, **kwargs):
        self.calls.append(kwargs)
        return self

    def execute(self):
        return {}

    def __getattr__(self, name):
        raise AssertionError(f"forbidden Gmail API method requested: {name}")


class FakeService:
    def __init__(self):
        self.messages_api = FakeMessages()

    def users(self):
        return self

    def messages(self):
        return self.messages_api


class CliProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "state.sqlite3"
        self.service = FakeService()
        self.message = GmailMessage(
            account_id="professional-demo", message_id="cli-local-1", thread_id="thread-1",
            received_at="2026-09-26T09:00:00Z", sender="sender@example.com",
            recipient="santiago@example.com", subject="Asunto", body="Cuerpo simulado",
        )

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, raw, guard_class=GmailReadStateGuard):
        client = Mock()
        client.get_message.return_value = self.message
        argv = [
            "cli.py", "process", "--account", self.message.account_id,
            "--message-id", self.message.message_id,
            "--client-secrets", "/tmp/client_secret.json",
            "--token-path", "/tmp/token.json",
            "--database", str(self.database),
        ]
        with (
            patch.object(sys, "argv", argv),
            patch.object(cli, "authorize", return_value=object()),
            patch.object(cli, "build_service", return_value=self.service),
            patch.object(cli, "GmailReadonlyClient", return_value=client),
            patch.object(cli, "run_mail_reader", return_value=raw),
            patch.object(cli, "GmailReadStateGuard", guard_class),
            redirect_stdout(io.StringIO()),
        ):
            cli.main()

    def test_no_importante_uses_guard_once_and_only_removes_unread(self):
        self.invoke(response())
        self.assertEqual(
            self.service.messages_api.calls,
            [{"userId": "me", "id": "cli-local-1", "body": {"removeLabelIds": ["UNREAD"]}}],
        )

    def test_importante_revision_injection_and_invalid_never_use_mutation(self):
        cases = [
            response("Entrevista", "IMPORTANTE", "P0"),
            response("Revisión", "REVISION", "P2"),
            response("Entrevista", "IMPORTANTE", "P0", True),
            "not json",
        ]
        for index, raw in enumerate(cases):
            self.message = GmailMessage(**{**self.message.__dict__, "message_id": f"cli-local-{index}"})
            self.database = Path(self.temp.name) / f"state-{index}.sqlite3"
            self.invoke(raw)
        self.assertEqual(self.service.messages_api.calls, [])
