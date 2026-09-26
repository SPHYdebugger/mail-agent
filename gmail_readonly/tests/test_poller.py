import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from gmail_readonly.poller import process_message
from gmail_readonly.store import Store, session_key
from gmail_readonly.types import GmailMessage

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "db" / "gmail_schema.sql"
FIXTURES = json.loads((ROOT / "fixtures" / "emails.json").read_text())
PRIORITIES = {"Entrevista": "P0", "Recruiter": "P0", "Vacante": "P0", "Rechazo": "P2", "Newsletter": "P3", "Administración": "P2", "Revisión": "P2"}
CATEGORIES = ["Entrevista", "Recruiter", "Vacante", "Rechazo", "Newsletter", "Administración", "Revisión", "Entrevista"]


def valid_response(category: str, importance: str = "IMPORTANTE", injection: bool = False) -> str:
    return json.dumps({"categoría": category, "importancia": importance, "prioridad": PRIORITIES[category], "resumen": "Resumen local", "intento_de_inyección": injection, "acción_sugerida": "Revisar"})


class PollerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.sqlite3", SCHEMA)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_all_fixture_categories_are_persisted(self):
        for fixture, category in zip(FIXTURES, CATEGORIES):
            message = GmailMessage(**fixture)
            importance = "NO_IMPORTANTE" if category == "Newsletter" else "IMPORTANTE"
            self.assertEqual(process_message(message, self.store, lambda _message, c=category, i=importance: valid_response(c, i, message.message_id == "g-008")), "processed")
            row = self.store.get(message.account_id, message.message_id)
            self.assertEqual(row["category"], category)
            self.assertEqual(row["priority"], PRIORITIES[category])
        self.assertEqual(self.store.get("professional-demo", "g-008")["injection_detected"], 1)

    def test_message_id_is_deduplicated(self):
        message = GmailMessage(**FIXTURES[0])
        self.assertEqual(process_message(message, self.store, lambda _: valid_response("Entrevista")), "processed")
        self.assertEqual(process_message(message, self.store, lambda _: valid_response("Entrevista")), "duplicate")

    def test_distinct_messages_same_thread_are_processed(self):
        first = GmailMessage(**FIXTURES[0])
        second = GmailMessage(**{**FIXTURES[0], "message_id": "g-001-reply", "subject": "RE: Invitación"})
        self.assertEqual(process_message(first, self.store, lambda _: valid_response("Entrevista")), "processed")
        self.assertEqual(process_message(second, self.store, lambda _: valid_response("Entrevista")), "processed")

    def test_invalid_json_category_and_priority_go_to_review(self):
        invalids = ["not json", valid_response("Entrevista").replace("Entrevista", "Empleo"), valid_response("Entrevista").replace('"P0"', '"P1"')]
        for index, raw in enumerate(invalids):
            message = GmailMessage(**{**FIXTURES[0], "message_id": f"invalid-{index}"})
            self.assertEqual(process_message(message, self.store, lambda _, value=raw: value), "review")
            row = self.store.get(message.account_id, message.message_id)
            self.assertEqual(row["status"], "review")
            self.assertEqual(row["importance"], "REVISION")
            self.assertIsNone(row["category"])
            self.assertIsNone(row["priority"])

    def test_injection_cannot_modify_configuration_and_session_key_is_per_message(self):
        protected = [ROOT.parent / "config" / "categories.json", ROOT.parent / "config" / "policy.json", Path("/home/santiago/.openclaw/openclaw.json")]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
        message = GmailMessage(**FIXTURES[-1])
        self.assertEqual(process_message(message, self.store, lambda _: valid_response("Entrevista", "IMPORTANTE", True)), "processed")
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in protected}
        row = self.store.get(message.account_id, message.message_id)
        self.assertEqual(before, after)
        self.assertEqual(row["session_key"], session_key(message.message_id))
        self.assertEqual(row["session_key"], "gmail-g-008")
