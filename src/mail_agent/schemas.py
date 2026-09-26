from dataclasses import dataclass


@dataclass(frozen=True)
class Email:
    account_id: str
    message_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    received_at: str


@dataclass(frozen=True)
class Classification:
    category: str
    priority: str
    label: str
    summary: str
    confidence: float
    injection_detected: bool
    should_notify: bool
