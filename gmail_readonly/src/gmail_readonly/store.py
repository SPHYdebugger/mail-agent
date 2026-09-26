import sqlite3
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .types import GmailMessage, MailReaderResult


def session_key(message_id: str) -> str:
    return f"gmail-{message_id}"


class Store:
    def __init__(self, database_path: Path, schema_path: Path):
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(schema_path.read_text(encoding="utf-8"))

    def close(self) -> None:
        self.connection.close()

    def claim(self, message: GmailMessage) -> bool:
        """Atomically reserve a Gmail message. Its body is never persisted."""
        with self.connection:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO gmail_messages
                (account_id,message_id,thread_id,received_at,sender,recipient,subject,session_key,status)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (message.account_id, message.message_id, message.thread_id, message.received_at,
                 message.sender, message.recipient, message.subject, session_key(message.message_id), "processing"),
            )
        return cursor.rowcount == 1

    def mark_processed(self, account_id: str, message_id: str, result: MailReaderResult) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET status='processed',category=?,importance=?,priority=?,summary=?,
                injection_detected=?,suggested_action=?,gmail_read_state=?,processed_at=?,validation_error=NULL
                WHERE account_id=? AND message_id=?""",
                (result.category, result.importance, result.priority, result.summary, int(result.injection_detected),
                 result.suggested_action, "pending" if result.importance == "NO_IMPORTANTE" else "not_requested",
                 _now(), account_id, message_id),
            )

    def mark_review(self, account_id: str, message_id: str, error: str) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET status='review',importance='REVISION',validation_error=?,processed_at=?
                WHERE account_id=? AND message_id=?""",
                (error, _now(), account_id, message_id),
            )

    def mark_read_applied(self, account_id: str, message_id: str) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET gmail_read_state='applied',gmail_read_at=?
                WHERE account_id=? AND message_id=? AND gmail_read_state='pending'""",
                (_now(), account_id, message_id),
            )

    def mark_read_failed(self, account_id: str, message_id: str) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET gmail_read_state='failed'
                WHERE account_id=? AND message_id=? AND gmail_read_state='pending'""",
                (account_id, message_id),
            )

    def queue_immediate_alert(self, account_id: str, message_id: str) -> None:
        row = self.get(account_id, message_id)
        if row is None:
            raise ValueError("message is not stored")
        with self.connection:
            self.connection.execute(
                """INSERT OR IGNORE INTO notification_outbox
                (account_id,notification_kind,message_id,importance,category,priority,summary,scheduled_for)
                VALUES (?,?,?,?,?,?,?,?)""",
                (account_id, "immediate_alert", message_id, row["importance"], row["category"],
                 row["priority"], row["summary"], _now()),
            )
            self.connection.execute(
                """UPDATE gmail_messages SET notification_state='queued',notification_queued_at=?
                WHERE account_id=? AND message_id=?""",
                (_now(), account_id, message_id),
            )

    def queue_daily_summaries(self, account_id: str, summary_date: date) -> None:
        """Queue local summary jobs. Delivery is intentionally not implemented."""
        madrid = ZoneInfo("Europe/Madrid")
        with self.connection:
            for hour in (12, 16, 21):
                scheduled = datetime.combine(summary_date, time(hour), tzinfo=madrid).isoformat()
                self.connection.execute(
                    """INSERT OR IGNORE INTO notification_outbox
                    (account_id,notification_kind,message_id,scheduled_for,timezone)
                    VALUES (?,?,?,?,?)""",
                    (account_id, "daily_summary", f"daily-{summary_date.isoformat()}-{hour:02d}",
                     scheduled, "Europe/Madrid"),
                )

    def outbox(self):
        return self.connection.execute("SELECT * FROM notification_outbox ORDER BY id").fetchall()

    def get(self, account_id: str, message_id: str):
        return self.connection.execute(
            "SELECT * FROM gmail_messages WHERE account_id=? AND message_id=?", (account_id, message_id)
        ).fetchone()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
