import subprocess
import unittest
from unittest.mock import patch

from gmail_readonly.mail_reader_client import MailReaderExecutionError, run_mail_reader
from gmail_readonly.types import GmailMessage


class MailReaderClientTests(unittest.TestCase):
    def setUp(self):
        self.message = GmailMessage("a", "m", "t", "d", "sender", "recipient", "subject", "body")

    def test_safe_execution_error_categories(self):
        cases = [
            (FileNotFoundError(), "reader_command_not_found"),
            (subprocess.TimeoutExpired(["openclaw"], 120), "reader_timeout"),
            (subprocess.CalledProcessError(7, ["openclaw"], stderr="secret"), "reader_exit_code_7"),
            (RuntimeError("secret"), "reader_unexpected_error"),
        ]
        for error, expected in cases:
            with patch("gmail_readonly.mail_reader_client.subprocess.run", side_effect=error):
                with self.assertRaisesRegex(MailReaderExecutionError, expected) as caught:
                    run_mail_reader(self.message)
                self.assertNotIn("secret", str(caught.exception))
