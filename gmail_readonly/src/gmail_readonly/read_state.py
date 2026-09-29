"""Apply the read-state policy to an already validated stored decision."""
from .validator import CATEGORIES, IMPORTANCE_VALUES, PRIORITIES


def is_eligible_no_importante(row) -> bool:
    """Use the same category and priority rules as response validation."""
    category = row["category"]
    priority = row["priority"]
    importance = row["importance"]
    return (
        row["status"] == "processed"
        and importance == "NO_IMPORTANTE"
        and importance in IMPORTANCE_VALUES
        and category in CATEGORIES
        and priority in PRIORITIES
        and row["injection_detected"] == 0
        and isinstance(row["summary"], str) and bool(row["summary"].strip())
        and isinstance(row["suggested_action"], str) and bool(row["suggested_action"].strip())
    )


def apply_processed_read_state(account_id, message_id, store, gmail_components):
    """Apply only the closed UNREAD removal after local eligibility checks."""
    row = store.get(account_id, message_id)
    if row is None:
        return "not_found"
    if row["gmail_read_state"] == "applied":
        return "already_applied"
    if not is_eligible_no_importante(row):
        store.mark_read_not_requested(account_id, message_id)
        return "not_allowed"

    client, gmail_guard = gmail_components()
    if "UNREAD" not in client.get_label_ids(message_id):
        store.mark_read_already_applied(account_id, message_id)
        return "already_applied"

    store.mark_read_pending(account_id, message_id)
    try:
        gmail_guard.mark_as_read(message_id)
    except Exception:
        store.mark_read_failed(account_id, message_id)
        return "failed"
    store.mark_read_applied(account_id, message_id)
    return "applied"
