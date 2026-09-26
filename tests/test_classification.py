import json
import unittest
from pathlib import Path

from mail_agent.classifier import classify
from mail_agent.schemas import Email

ROOT = Path(__file__).resolve().parents[1]


class ClassificationTests(unittest.TestCase):
    def test_all_fixture_categories_and_p0(self):
        expected = json.loads((ROOT / "fixtures" / "expected.json").read_text())
        fixtures = json.loads((ROOT / "fixtures" / "emails.json").read_text())
        results = {item["message_id"]: classify(Email(**item)) for item in fixtures}
        self.assertEqual({key: value.category for key, value in results.items()}, expected)
        for message_id in ("m-001", "m-002", "m-003", "m-010"):
            self.assertEqual(results[message_id].priority, "P0")
            self.assertTrue(results[message_id].should_notify)

    def test_summary_is_deterministic(self):
        email = Email(**json.loads((ROOT / "fixtures" / "emails.json").read_text())[0])
        self.assertEqual(classify(email).summary, classify(email).summary)

    def test_malicious_content_is_detected_as_data(self):
        fixtures = {item["message_id"]: Email(**item) for item in json.loads((ROOT / "fixtures" / "emails.json").read_text())}
        for message_id in ("m-008", "m-009", "m-010", "m-011"):
            self.assertTrue(classify(fixtures[message_id]).injection_detected)
