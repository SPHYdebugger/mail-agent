"""Gmail read adapter. Gmail mutations are isolated in gmail_mutation_guard."""
from email.utils import parsedate_to_datetime

from .mime_text import extract_text
from .types import GmailMessage


class GmailReadonlyClient:
    def __init__(self, service, account_id: str):
        self.service = service
        self.account_id = account_id

    def list_inbox_ids(self, max_results: int = 25) -> list[str]:
        response = self.service.users().messages().list(
            userId="me", labelIds=["INBOX"], includeSpamTrash=False, maxResults=max_results
        ).execute()
        return [item["id"] for item in response.get("messages", [])]

    def get_metadata(self, message_id: str) -> dict[str, str]:
        raw = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["Date", "From", "Subject"],
        ).execute()
        headers = {item["name"].lower(): item["value"] for item in raw.get("payload", {}).get("headers", [])}
        date = headers.get("date", "")
        try:
            received_at = parsedate_to_datetime(date).isoformat()
        except (TypeError, ValueError):
            received_at = date
        return {
            "messageId": raw["id"],
            "threadId": raw["threadId"],
            "fecha": received_at,
            "remitente": headers.get("from", ""),
            "asunto": headers.get("subject", ""),
        }

    def get_label_ids(self, message_id: str) -> list[str]:
        raw = self.service.users().messages().get(
            userId="me",
            id=message_id,
            format="minimal",
        ).execute()
        return raw.get("labelIds", [])

    def get_message(self, message_id: str) -> GmailMessage:
        raw = self.service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {item["name"].lower(): item["value"] for item in raw.get("payload", {}).get("headers", [])}
        date = headers.get("date", "")
        try:
            received_at = parsedate_to_datetime(date).isoformat()
        except (TypeError, ValueError):
            received_at = date
        return GmailMessage(
            account_id=self.account_id, message_id=raw["id"], thread_id=raw["threadId"],
            received_at=received_at, sender=headers.get("from", ""), recipient=headers.get("to", ""),
            subject=headers.get("subject", ""), body=extract_text(raw.get("payload", {})),
        )
