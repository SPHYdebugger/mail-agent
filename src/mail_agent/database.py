import json
import sqlite3
from pathlib import Path

from .schemas import Classification, Email


class Database:
    def __init__(self, database_path: Path, schema_path: Path):
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(schema_path.read_text(encoding="utf-8"))

    def close(self) -> None:
        self.connection.close()

    def process(self, email: Email, result: Classification, recipient: str) -> bool:
        """Returns False for an already processed message; no outbound delivery exists."""
        with self.connection:
            cursor = self.connection.execute(
                """INSERT OR IGNORE INTO messages
                (account_id,message_id,thread_id,sender,subject,body,received_at,processing_state)
                VALUES (?,?,?,?,?,?,?,?)""",
                (email.account_id, email.message_id, email.thread_id, email.sender, email.subject,
                 email.body, email.received_at, "classified"),
            )
            if cursor.rowcount == 0:
                return False
            message_row_id = cursor.lastrowid
            self.connection.execute(
                """INSERT INTO classifications
                (message_row_id,category,priority,label,summary,confidence,injection_detected)
                VALUES (?,?,?,?,?,?,?)""",
                (message_row_id, result.category, result.priority, result.label, result.summary,
                 result.confidence, int(result.injection_detected)),
            )
            self.connection.execute("INSERT INTO message_labels (message_row_id,label) VALUES (?,?)", (message_row_id, result.label))
            if result.should_notify:
                payload = json.dumps({"priority": result.priority, "summary": result.summary}, ensure_ascii=False)
                self.connection.execute(
                    "INSERT INTO notifications (message_row_id,recipient,status,payload) VALUES (?,?,?,?)",
                    (message_row_id, recipient, "simulated_recorded", payload),
                )
        return True

    def report_rows(self):
        return self.connection.execute(
            """SELECT m.message_id,m.subject,c.category,c.priority,c.label,c.summary,
                      c.injection_detected,n.status AS notification_status
               FROM messages m JOIN classifications c ON c.message_row_id=m.id
               LEFT JOIN notifications n ON n.message_row_id=m.id ORDER BY m.message_id"""
        ).fetchall()
