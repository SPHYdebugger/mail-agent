import tempfile
import unittest
from pathlib import Path

from gmail_readonly.read_state import apply_processed_read_state
from gmail_readonly.store import Store
from gmail_readonly.types import GmailMessage, MailReaderResult

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "gmail_schema.sql"


class FakeClient:
    def __init__(self, labels):
        self.labels = labels
        self.calls = []

    def get_label_ids(self, message_id):
        self.calls.append(message_id)
        return self.labels

    def get_message(self, message_id):
        raise AssertionError("message body must not be requested")


class FakeGuard:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def mark_as_read(self, message_id):
        self.calls.append(message_id)
        if self.fail:
            raise RuntimeError("simulated mutation failure")


class ApplyReadStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.sqlite3", SCHEMA)
        self.message = GmailMessage(
            account_id="professional-demo", message_id="apply-1", thread_id="thread-1",
            received_at="2026-09-26T09:00:00Z", sender="sender@example.com",
            recipient="santiago@example.com", subject="Asunto", body="not persisted",
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def add_processed(self, category="Newsletter", importance="NO_IMPORTANTE", priority="P3", injection=False):
        self.assertTrue(self.store.claim(self.message))
        self.store.mark_processed(
            self.message.account_id,
            self.message.message_id,
            MailReaderResult(category, importance, priority, "Resumen", injection, "Revisar"),
        )

    def components(self, labels=("UNREAD",)):
        self.client = FakeClient(list(labels))
        self.guard = FakeGuard()
        self.factory_calls = 0

        def factory():
            self.factory_calls += 1
            return self.client, self.guard

        return factory

    def test_eligible_unread_mutates_once(self):
        self.add_processed()
        result = apply_processed_read_state(self.message.account_id, self.message.message_id, self.store, self.components())
        self.assertEqual(result, "applied")
        self.assertEqual(self.client.calls, [self.message.message_id])
        self.assertEqual(self.guard.calls, [self.message.message_id])
        self.assertEqual(self.store.get(self.message.account_id, self.message.message_id)["gmail_read_state"], "applied")

    def test_eligible_already_read_never_mutates(self):
        self.add_processed()
        result = apply_processed_read_state(self.message.account_id, self.message.message_id, self.store, self.components(("INBOX",)))
        self.assertEqual(result, "already_applied")
        self.assertEqual(self.client.calls, [self.message.message_id])
        self.assertEqual(self.guard.calls, [])
        self.assertEqual(self.store.get(self.message.account_id, self.message.message_id)["gmail_read_state"], "applied")

    def test_applied_is_terminal_without_gmail_lookup(self):
        self.add_processed()
        self.store.mark_read_already_applied(self.message.account_id, self.message.message_id)
        factory = self.components()
        self.assertEqual(apply_processed_read_state(self.message.account_id, self.message.message_id, self.store, factory), "already_applied")
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(self.client.calls, [])
        self.assertEqual(self.guard.calls, [])

    def test_failed_eligible_decision_can_retry(self):
        self.add_processed()
        self.store.mark_read_pending(self.message.account_id, self.message.message_id)
        self.store.mark_read_failed(self.message.account_id, self.message.message_id)
        self.assertEqual(self.store.get(self.message.account_id, self.message.message_id)["gmail_read_state"], "failed")
        self.assertEqual(apply_processed_read_state(self.message.account_id, self.message.message_id, self.store, self.components()), "applied")
        self.assertEqual(self.client.calls, [self.message.message_id])
        self.assertEqual(self.guard.calls, [self.message.message_id])

    def test_non_eligible_records_never_create_gmail_components(self):
        cases = [
            ("Entrevista", "IMPORTANTE", "P0", False),
            ("Revisión", "REVISION", "P2", False),
            ("Newsletter", "NO_IMPORTANTE", "P3", True),
        ]
        for index, case in enumerate(cases):
            self.message = GmailMessage(**{**self.message.__dict__, "message_id": f"not-allowed-{index}"})
            self.add_processed(*case)
            factory = self.components()
            self.assertEqual(apply_processed_read_state(self.message.account_id, self.message.message_id, self.store, factory), "not_allowed")
            self.assertEqual(self.factory_calls, 0)
            self.assertEqual(self.client.calls, [])
            self.assertEqual(self.guard.calls, [])

    def test_not_found_never_creates_gmail_components(self):
        factory = self.components()
        self.assertEqual(apply_processed_read_state("professional-demo", "missing", self.store, factory), "not_found")
        self.assertEqual(self.factory_calls, 0)
        self.assertEqual(self.client.calls, [])
