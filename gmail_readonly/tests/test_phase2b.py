import inspect
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gmail_readonly.gmail_mutation_guard import GmailReadStateGuard
from gmail_readonly.poller import process_message
from gmail_readonly.store import Store
from gmail_readonly.types import GmailMessage

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "gmail_schema.sql"


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


class FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class FakeService:
    def __init__(self):
        self.messages_api = FakeMessages()

    def users(self):
        return FakeUsers(self.messages_api)


class ObservingGuard:
    def __init__(self, store, delegate, account_id):
        self.store = store
        self.delegate = delegate
        self.account_id = account_id
        self.states = []

    def mark_as_read(self, message_id):
        self.states.append(self.store.get(self.account_id, message_id)["gmail_read_state"])
        self.delegate.mark_as_read(message_id)


class FailingGuard:
    def __init__(self, store, account_id):
        self.store = store
        self.account_id = account_id
        self.states = []

    def mark_as_read(self, message_id):
        self.states.append(self.store.get(self.account_id, message_id)["gmail_read_state"])
        raise RuntimeError("simulated Gmail failure")


class Phase2BTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.sqlite3", SCHEMA)
        self.message = GmailMessage(
            account_id="professional-demo", message_id="local-1", thread_id="thread-1",
            received_at="2026-09-26T09:00:00Z", sender="sender@example.com",
            recipient="santiago@example.com", subject="Asunto", body="Cuerpo no persistido",
        )
        self.service = FakeService()
        self.guard = GmailReadStateGuard(self.service)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_no_importante_removes_only_unread(self):
        guard = ObservingGuard(self.store, self.guard, self.message.account_id)
        self.assertEqual(process_message(self.message, self.store, lambda _: response(), guard), "processed")
        self.assertEqual(guard.states, ["pending"])
        self.assertEqual(self.service.messages_api.calls, [{"userId": "me", "id": "local-1", "body": {"removeLabelIds": ["UNREAD"]}}])
        self.assertEqual(self.store.get("professional-demo", "local-1")["gmail_read_state"], "applied")
        self.assertEqual(self.store.outbox(), [])

    def test_no_importante_without_guard_remains_not_requested(self):
        self.assertEqual(process_message(self.message, self.store, lambda _: response()), "processed")
        row = self.store.get(self.message.account_id, self.message.message_id)
        self.assertEqual(row["gmail_read_state"], "not_requested")
        self.assertEqual(self.service.messages_api.calls, [])

    def test_no_importante_guard_failure_transitions_pending_to_failed(self):
        guard = FailingGuard(self.store, self.message.account_id)
        self.assertEqual(process_message(self.message, self.store, lambda _: response(), guard), "processed_read_failed")
        self.assertEqual(guard.states, ["pending"])
        self.assertEqual(self.store.get(self.message.account_id, self.message.message_id)["gmail_read_state"], "failed")
        self.assertEqual(self.service.messages_api.calls, [])

    def test_importante_revision_and_injection_never_modify_gmail(self):
        cases = [
            ("important", response("Entrevista", "IMPORTANTE", "P0")),
            ("revision", response("Revisión", "REVISION", "P2")),
            ("injection", response("Entrevista", "IMPORTANTE", "P0", True)),
        ]
        for suffix, raw in cases:
            message = GmailMessage(**{**self.message.__dict__, "message_id": suffix})
            self.assertEqual(process_message(message, self.store, lambda _, value=raw: value, self.guard), "processed")
        self.assertEqual(self.service.messages_api.calls, [])
        self.assertEqual([row["notification_kind"] for row in self.store.outbox()], ["immediate_alert"] * 3)

    def test_p0_categories_never_mark_as_read(self):
        for category in ("Entrevista", "Recruiter", "Candidatura"):
            message = GmailMessage(**{**self.message.__dict__, "message_id": f"p0-{category}"})
            raw = response(category, "IMPORTANTE", "P0")
            self.assertEqual(process_message(message, self.store, lambda _, value=raw: value, self.guard), "processed")
            self.assertEqual(self.store.get(message.account_id, message.message_id)["gmail_read_state"], "not_requested")
        self.assertEqual(self.service.messages_api.calls, [])

    def test_invalid_outputs_become_revision_and_never_modify_gmail(self):
        invalids = [
            "not json",
            response(category="Other"),
            response(priority="P1"),
            response(importance="MAYBE"),
            response("Entrevista", "NO_IMPORTANTE", "P0"),
            response("Newsletter", "NO_IMPORTANTE", "P3", True),
        ]
        for index, raw in enumerate(invalids):
            message = GmailMessage(**{**self.message.__dict__, "message_id": f"invalid-{index}"})
            self.assertEqual(process_message(message, self.store, lambda _, value=raw: value, self.guard), "review")
            row = self.store.get(message.account_id, message.message_id)
            self.assertEqual(row["importance"], "REVISION")
            self.assertEqual(row["gmail_read_state"], "not_requested")
        self.assertEqual(self.service.messages_api.calls, [])
        self.assertEqual(len(self.store.outbox()), len(invalids))

    def test_guard_has_one_closed_mutation_surface(self):
        self.assertEqual([name for name in dir(self.guard) if not name.startswith("_")], ["mark_as_read"])
        source = inspect.getsource(GmailReadStateGuard)
        for forbidden in ("addLabelIds", ".send(", ".trash(", ".delete(", ".drafts(", ".batchModify(", ".threads(", ".archive(", ".move("):
            self.assertNotIn(forbidden, source)
        with self.assertRaises(ValueError):
            self.guard.mark_as_read("")

    def test_message_id_deduplication_prevents_a_second_mutation(self):
        self.assertEqual(process_message(self.message, self.store, lambda _: response(), self.guard), "processed")
        self.assertEqual(process_message(self.message, self.store, lambda _: response(), self.guard), "duplicate")
        self.assertEqual(len(self.service.messages_api.calls), 1)

    def test_daily_summary_jobs_are_local_and_use_madrid_schedule(self):
        self.store.queue_daily_summaries("professional-demo", date(2026, 9, 26))
        summaries = self.store.outbox()
        self.assertEqual(len(summaries), 3)
        self.assertEqual([row["notification_kind"] for row in summaries], ["daily_summary"] * 3)
        self.assertEqual([row["scheduled_for"][-6:] for row in summaries], ["+02:00"] * 3)
        self.assertEqual([row["scheduled_for"][11:16] for row in summaries], ["12:00", "16:00", "21:00"])
        self.assertEqual({row["timezone"] for row in summaries}, {"Europe/Madrid"})
