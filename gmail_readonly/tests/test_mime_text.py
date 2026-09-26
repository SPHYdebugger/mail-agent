import base64
import unittest

from gmail_readonly.mime_text import extract_text


def encoded(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


class MimeTextTests(unittest.TestCase):
    def test_prefers_plain_text_and_ignores_attachment(self):
        payload = {"mimeType": "multipart/mixed", "parts": [
            {"mimeType": "text/plain", "body": {"data": encoded("mensaje visible")}},
            {"mimeType": "text/plain", "filename": "secret.txt", "body": {"attachmentId": "a1", "data": encoded("adjunto")}},
        ]}
        self.assertEqual(extract_text(payload), "mensaje visible")

    def test_html_fallback_strips_markup(self):
        payload = {"mimeType": "text/html", "body": {"data": encoded("<p>Hola <b>mundo</b></p><script>bad()</script>")}}
        self.assertEqual(extract_text(payload), "Hola mundo")
