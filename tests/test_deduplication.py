import json
import tempfile
import unittest
from pathlib import Path

from mail_agent.classifier import classify
from mail_agent.database import Database
from mail_agent.schemas import Email

ROOT = Path(__file__).resolve().parents[1]


class DeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temp_dir.name) / "test.sqlite3", ROOT / "db" / "schema.sql")
        self.policy = json.loads((ROOT / "config" / "policy.json").read_text())
        self.email_data = json.loads((ROOT / "fixtures" / "emails.json").read_text())[0]

    def tearDown(self):
        self.database.close()
        self.temp_dir.cleanup()

    def test_same_account_and_message_id_is_processed_once(self):
        email = Email(**self.email_data)
        recipient = self.policy["notification"]["allowed_recipient"]
        self.assertTrue(self.database.process(email, classify(email), recipient))
        self.assertFalse(self.database.process(email, classify(email), recipient))
        self.assertEqual(len(self.database.report_rows()), 1)

    def test_new_message_in_same_thread_is_processed(self):
        first = Email(**self.email_data)
        second_data = {**self.email_data, "message_id": "m-001-reply", "subject": "RE: Invitación a entrevista técnica"}
        second = Email(**second_data)
        recipient = self.policy["notification"]["allowed_recipient"]
        self.assertTrue(self.database.process(first, classify(first), recipient))
        self.assertTrue(self.database.process(second, classify(second), recipient))
        self.assertEqual(len(self.database.report_rows()), 2)
