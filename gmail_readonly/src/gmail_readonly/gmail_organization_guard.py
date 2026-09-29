"""Closed Gmail mutation surface for authorized automatic organization."""
from .organization import TARGET_LABELS

class GmailOrganizationGuard:
    def __init__(self, service, label_ids):
        if set(label_ids) != set(TARGET_LABELS):
            raise ValueError("authorized labels incomplete")
        self._service, self._label_ids = service, dict(label_ids)

    def organize(self, message_id, target):
        if target not in self._label_ids or not isinstance(message_id, str) or not message_id.strip():
            raise ValueError("unauthorized organization target")
        labels=[self._label_ids["no_importantes"]]
        if target != "no_importantes": labels.append(self._label_ids[target])
        self._service.users().messages().modify(userId="me", id=message_id, body={"addLabelIds": labels, "removeLabelIds": ["INBOX", "UNREAD"]}).execute()

def ensure_organization_labels(service):
    existing = {x.get("name"): x.get("id") for x in service.users().labels().list(userId="me").execute().get("labels", [])}
    resolved = {}
    for target, name in TARGET_LABELS.items():
        if name not in existing:
            existing[name] = service.users().labels().create(userId="me", body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}).execute()["id"]
        resolved[target] = existing[name]
    return resolved
