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
        self._migrate_organization_columns()
        self._migrate_notification_columns()

    def _migrate_organization_columns(self) -> None:
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(gmail_messages)")}
        for name, definition in (("organization_state", "TEXT NOT NULL DEFAULT 'not_requested'"),
                                 ("organization_label", "TEXT"), ("organized_at", "TEXT")):
            if name not in columns:
                self.connection.execute(f"ALTER TABLE gmail_messages ADD COLUMN {name} {definition}")

    def _migrate_notification_columns(self) -> None:
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(notification_outbox)")}
        for name, definition in (("sent_at", "TEXT"), ("last_error", "TEXT"), ("attempts", "INTEGER NOT NULL DEFAULT 0")):
            if name not in columns:
                self.connection.execute(f"ALTER TABLE notification_outbox ADD COLUMN {name} {definition}")
        sql = self.connection.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='notification_outbox'").fetchone()[0]
        if "'sent'" not in sql:
            with self.connection:
                self.connection.executescript("""ALTER TABLE notification_outbox RENAME TO notification_outbox_old;
                CREATE TABLE notification_outbox (id INTEGER PRIMARY KEY,account_id TEXT NOT NULL,notification_kind TEXT NOT NULL CHECK(notification_kind IN ('immediate_alert','daily_summary')),message_id TEXT,importance TEXT CHECK(importance IN ('IMPORTANTE','NO_IMPORTANTE','REVISION')),category TEXT,priority TEXT,summary TEXT,scheduled_for TEXT NOT NULL,timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','failed')),sent_at TEXT,last_error TEXT,attempts INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(account_id,notification_kind,message_id,scheduled_for));
                INSERT INTO notification_outbox SELECT id,account_id,notification_kind,message_id,importance,category,priority,summary,scheduled_for,timezone,CASE WHEN status='delivered' THEN 'sent' ELSE status END,sent_at,last_error,attempts,created_at FROM notification_outbox_old;
                DROP TABLE notification_outbox_old;
                CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending ON notification_outbox(status, scheduled_for);""")

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
                 result.suggested_action, "not_requested",
                 _now(), account_id, message_id),
            )

    def mark_read_pending(self, account_id: str, message_id: str) -> None:
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET gmail_read_state='pending'
                WHERE account_id=? AND message_id=?
                AND gmail_read_state IN ('not_requested', 'failed')""",
                (account_id, message_id),
            )

    def mark_read_not_requested(self, account_id: str, message_id: str) -> None:
        """Clear a non-terminal, inapplicable request without changing applied/failed."""
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET gmail_read_state='not_requested'
                WHERE account_id=? AND message_id=?
                AND gmail_read_state IN ('not_requested', 'pending')""",
                (account_id, message_id),
            )

    def mark_read_already_applied(self, account_id: str, message_id: str) -> None:
        """Record the observed Gmail state without performing a Gmail mutation."""
        with self.connection:
            self.connection.execute(
                """UPDATE gmail_messages SET gmail_read_state='applied',gmail_read_at=?
                WHERE account_id=? AND message_id=? AND gmail_read_state != 'applied'""",
                (_now(), account_id, message_id),
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

    def mark_organization_pending(self, account_id, message_id, label):
        with self.connection:
            self.connection.execute("UPDATE gmail_messages SET organization_state='pending',organization_label=? WHERE account_id=? AND message_id=? AND organization_state IN ('not_requested','failed')", (label, account_id, message_id))

    def mark_organization_applied(self, account_id, message_id):
        with self.connection:
            self.connection.execute("UPDATE gmail_messages SET organization_state='applied',organized_at=?,gmail_read_state='applied',gmail_read_at=? WHERE account_id=? AND message_id=? AND organization_state='pending'", (_now(), _now(), account_id, message_id))

    def mark_organization_failed(self, account_id, message_id):
        with self.connection:
            self.connection.execute("UPDATE gmail_messages SET organization_state='failed' WHERE account_id=? AND message_id=? AND organization_state='pending'", (account_id, message_id))

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

    def claim_notifications(self):
        rows=[]
        with self.connection:
            for row in self.connection.execute("SELECT o.*,m.sender,m.subject,m.suggested_action FROM notification_outbox o LEFT JOIN gmail_messages m ON m.account_id=o.account_id AND m.message_id=o.message_id WHERE o.status IN ('pending','failed') AND o.notification_kind='immediate_alert' ORDER BY o.id").fetchall():
                if self.connection.execute("UPDATE notification_outbox SET status='sending',attempts=attempts+1,last_error=NULL WHERE id=? AND status IN ('pending','failed')", (row['id'],)).rowcount:
                    rows.append(row)
        return rows

    def mark_notification_sent(self, notification_id):
        with self.connection:
            self.connection.execute("UPDATE notification_outbox SET status='sent',sent_at=? WHERE id=? AND status='sending'", (_now(), notification_id))

    def mark_notification_failed(self, notification_id, error):
        with self.connection:
            self.connection.execute("UPDATE notification_outbox SET status='failed',last_error=? WHERE id=? AND status='sending'", (error[:500], notification_id))

    def record_poll_error(self, account_id: str, message_id: str, error: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO poll_errors (account_id,message_id,error) VALUES (?,?,?)",
                (account_id, message_id, error),
            )

    def poll_errors(self):
        return self.connection.execute("SELECT * FROM poll_errors ORDER BY id").fetchall()

    def get(self, account_id: str, message_id: str):
        return self.connection.execute(
            "SELECT * FROM gmail_messages WHERE account_id=? AND message_id=?", (account_id, message_id)
        ).fetchone()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
