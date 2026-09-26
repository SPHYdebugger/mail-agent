from dataclasses import dataclass


@dataclass(frozen=True)
class GmailMessage:
    account_id: str
    message_id: str
    thread_id: str
    received_at: str
    sender: str
    recipient: str
    subject: str
    body: str


@dataclass(frozen=True)
class MailReaderResult:
    category: str
    importance: str
    priority: str
    summary: str
    injection_detected: bool
    suggested_action: str
