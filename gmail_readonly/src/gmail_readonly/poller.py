"""Controlled one-shot polling orchestration."""
from .types import GmailMessage
from .validator import ResponseValidationError, validate_response
from .organization import TARGET_LABELS, determine_organization_target
from .mail_reader_client import MailReaderExecutionError


def poll_once(client, store, reader, gmail_guard, max_results: int = 25, organization_guard=None) -> dict[str, int]:
    """Run one finite INBOX pass. Known messages are never fetched again."""
    summary = {
        "found": 0,
        "already_known": 0,
        "new": 0,
        "processed": 0,
        "important": 0,
        "review": 0,
        "no_importante": 0,
        "marked_read": 0,
        "errors": 0,
    }
    message_ids = client.list_inbox_ids(max_results)
    summary["found"] = len(message_ids)
    for message_id in message_ids:
        if store.get(client.account_id, message_id) is not None:
            summary["already_known"] += 1
            continue
        summary["new"] += 1
        try:
            message = client.get_message(message_id)
            outcome = process_message(message, store, reader, gmail_guard, organization_guard)
            row = store.get(message.account_id, message.message_id)
            if outcome == "duplicate":
                summary["already_known"] += 1
                continue
            if outcome == "processed_read_failed":
                summary["errors"] += 1
            else:
                summary["processed"] += 1
            if row["importance"] == "IMPORTANTE":
                summary["important"] += 1
            elif row["importance"] == "REVISION":
                summary["review"] += 1
            elif row["importance"] == "NO_IMPORTANTE":
                summary["no_importante"] += 1
            if row["gmail_read_state"] == "applied":
                summary["marked_read"] += 1
        except Exception as error:
            store.record_poll_error(client.account_id, message_id, "poll_failure")
            summary["errors"] += 1
    return summary


def process_message(message: GmailMessage, store, reader, gmail_guard=None, organization_guard=None) -> str:
    if not store.claim(message):
        return "duplicate"
    try:
        raw_response = reader(message)
        result = validate_response(raw_response)
    except ResponseValidationError as error:
        store.mark_review(message.account_id, message.message_id, str(error))
        store.queue_immediate_alert(message.account_id, message.message_id)
        return "review"
    except MailReaderExecutionError as error:
        store.mark_review(message.account_id, message.message_id, str(error))
        store.queue_immediate_alert(message.account_id, message.message_id)
        return "review"
    except Exception:
        store.mark_review(message.account_id, message.message_id, "reader_unexpected_error")
        store.queue_immediate_alert(message.account_id, message.message_id)
        return "review"
    store.mark_processed(message.account_id, message.message_id, result)
    if result.importance in {"IMPORTANTE", "REVISION"}:
        store.queue_immediate_alert(message.account_id, message.message_id)
    else:
        target = determine_organization_target(result, message)
        if organization_guard is not None:
            target = target or "no_importantes"
            store.mark_organization_pending(message.account_id, message.message_id, TARGET_LABELS[target])
            try:
                organization_guard.organize(message.message_id, target)
            except Exception:
                store.mark_organization_failed(message.account_id, message.message_id)
                return "processed_organization_failed"
            store.mark_organization_applied(message.account_id, message.message_id)
            return "processed"
        if gmail_guard is None:
            return "processed"
        store.mark_read_pending(message.account_id, message.message_id)
        try:
            gmail_guard.mark_as_read(message.message_id)
        except Exception:
            store.mark_read_failed(message.account_id, message.message_id)
            return "processed_read_failed"
        store.mark_read_applied(message.account_id, message.message_id)
    return "processed"
