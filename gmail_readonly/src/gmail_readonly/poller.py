"""Controlled one-shot polling orchestration."""
from .types import GmailMessage
from .validator import ResponseValidationError, validate_response
from .mail_reader_client import MailReaderExecutionError


def process_message(message: GmailMessage, store, reader, gmail_guard=None) -> str:
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
    elif gmail_guard is not None:
        try:
            gmail_guard.mark_as_read(message.message_id)
        except Exception:
            store.mark_read_failed(message.account_id, message.message_id)
            return "processed_read_failed"
        store.mark_read_applied(message.account_id, message.message_id)
    return "processed"
