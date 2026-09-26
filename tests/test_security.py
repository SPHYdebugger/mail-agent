import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from mail_agent.classifier import classify
from mail_agent.database import Database
from mail_agent.schemas import Email

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SecurityTests(unittest.TestCase):
    def test_email_content_cannot_change_configuration_or_future_recipient(self):
        protected = [ROOT / "config" / "policy.json", ROOT / "config" / "categories.json", ROOT / "agent" / "AGENTS.md"]
        before = {path: fingerprint(path) for path in protected}
        policy_before = json.loads((ROOT / "config" / "policy.json").read_text())
        malicious = [Email(**item) for item in json.loads((ROOT / "fixtures" / "emails.json").read_text()) if item["message_id"] in {"m-008", "m-009", "m-010", "m-011"}]
        with tempfile.TemporaryDirectory() as tmp:
            database = Database(Path(tmp) / "test.sqlite3", ROOT / "db" / "schema.sql")
            try:
                for email in malicious:
                    result = classify(email)
                    database.process(email, result, policy_before["notification"]["allowed_recipient"])
            finally:
                database.close()
        after = {path: fingerprint(path) for path in protected}
        policy_after = json.loads((ROOT / "config" / "policy.json").read_text())
        self.assertEqual(before, after)
        self.assertEqual(policy_before, policy_after)
        self.assertEqual(policy_after["notification"]["allowed_recipient"], "SIMULATED_LOCAL_ONLY")
        self.assertTrue(policy_after["configuration_writes_from_email"] is False)
        self.assertTrue(policy_after["email_send"] is False)
        self.assertTrue(policy_after["command_execution"] is False)

    def test_priority_is_not_overridden_by_malicious_text(self):
        email_data = next(item for item in json.loads((ROOT / "fixtures" / "emails.json").read_text()) if item["message_id"] == "m-010")
        result = classify(Email(**email_data))
        self.assertEqual(result.category, "interview")
        self.assertEqual(result.priority, "P0")
