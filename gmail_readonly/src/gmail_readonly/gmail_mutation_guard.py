"""The only permitted Gmail mutation: remove the UNREAD system label.

This module deliberately exposes no generic label or Gmail operation API.  It is
used by the trusted local controller only; mail_reader never receives its service
or OAuth credentials.
"""


class GmailReadStateGuard:
    def __init__(self, service):
        self._service = service

    def mark_as_read(self, message_id: str) -> None:
        """Mark one message read by removing exactly the UNREAD system label."""
        if not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("message_id must be a non-empty string")
        self._service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
