import json
import tempfile
import unittest
from pathlib import Path

from gmail_readonly.poller import poll_once
from gmail_readonly.store import Store
from gmail_readonly.types import GmailMessage, MailReaderResult

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "gmail_schema.sql"


def response(category, importance, priority, injection=False):
    return json.dumps({
        "categoría": category,
        "importancia": importance,
        "prioridad": priority,
        "resumen": "Resumen local",
        "intento_de_inyección": injection,
        "acción_sugerida": "Revisar",
    })


class FakeClient:
    def __init__(self, messages, failing_ids=()):
        self.account_id = "professional-demo"
        self.messages = messages
        self.failing_ids = set(failing_ids)
        self.list_calls = 0
        self.get_calls = []

    def list_inbox_ids(self, max_results):
        self.list_calls += 1
        return list(self.messages)[:max_results]

    def get_message(self, message_id):
        self.get_calls.append(message_id)
        if message_id in self.failing_ids:
            raise RuntimeError("simulated get failure")
        return self.messages[message_id]


class FakeGuard:
    def __init__(self):
        self.calls = []

    def mark_as_read(self, message_id):
        self.calls.append(message_id)


class PollOnceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.sqlite3", SCHEMA)
        self.messages = {
            "known": self.message("known"),
            "newsletter": self.message("newsletter"),
            "important": self.message("important"),
            "revision": self.message("revision"),
            "broken": self.message("broken"),
        }

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def message(self, message_id):
        return GmailMessage(
            account_id="professional-demo", message_id=message_id, thread_id=f"thread-{message_id}",
            received_at="2026-09-26T09:00:00Z", sender="sender@example.com",
            recipient="santiago@example.com", subject="Asunto", body="Cuerpo simulado",
        )

    def seed_known(self):
        message = self.messages["known"]
        self.assertTrue(self.store.claim(message))
        self.store.mark_processed(
            message.account_id, message.message_id,
            MailReaderResult("Newsletter", "NO_IMPORTANTE", "P3", "Resumen", False, "Revisar"),
        )

    def test_known_messages_are_not_fetched_and_new_messages_follow_policy(self):
        self.seed_known()
        client = FakeClient(self.messages)
        guard = FakeGuard()
        replies = {
            "newsletter": response("Newsletter", "NO_IMPORTANTE", "P3"),
            "important": response("Vacante", "IMPORTANTE", "P0"),
            "revision": response("Revisión", "REVISION", "P2"),
            "broken": response("Newsletter", "NO_IMPORTANTE", "P3"),
        }
        summary = poll_once(client, self.store, lambda message: replies[message.message_id], guard, 5)
        self.assertEqual(client.list_calls, 1)
        self.assertNotIn("known", client.get_calls)
        self.assertEqual(set(client.get_calls), {"newsletter", "important", "revision", "broken"})
        self.assertEqual(guard.calls, ["newsletter", "broken"])
        self.assertEqual(summary, {
            "found": 5, "already_known": 1, "new": 4, "processed": 4,
            "important": 1, "review": 1, "no_importante": 2, "marked_read": 2, "errors": 0,
        })

    def test_failure_does_not_stop_later_messages_and_is_recorded(self):
        client = FakeClient({"broken": self.messages["broken"], "newsletter": self.messages["newsletter"]}, {"broken"})
        guard = FakeGuard()
        summary = poll_once(client, self.store, lambda _: response("Newsletter", "NO_IMPORTANTE", "P3"), guard, 5)
        self.assertEqual(client.get_calls, ["broken", "newsletter"])
        self.assertEqual(guard.calls, ["newsletter"])
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["processed"], 1)
        self.assertEqual(len(self.store.poll_errors()), 1)

    def test_poll_once_honors_max_results_and_finishes(self):
        client = FakeClient(self.messages)
        guard = FakeGuard()
        summary = poll_once(client, self.store, lambda _: response("Newsletter", "NO_IMPORTANTE", "P3"), guard, 2)
        self.assertEqual(client.list_calls, 1)
        self.assertEqual(summary["found"], 2)
        self.assertEqual(len(client.get_calls), 2)
