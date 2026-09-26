PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS gmail_messages (
    id INTEGER PRIMARY KEY,
    account_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    received_at TEXT NOT NULL,
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    session_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing', 'processed', 'review', 'failed')),
    category TEXT,
    importance TEXT CHECK(importance IN ('IMPORTANTE', 'NO_IMPORTANTE', 'REVISION')),
    priority TEXT,
    summary TEXT,
    injection_detected INTEGER,
    suggested_action TEXT,
    validation_error TEXT,
    gmail_read_state TEXT NOT NULL DEFAULT 'not_requested'
        CHECK(gmail_read_state IN ('not_requested', 'pending', 'applied', 'failed')),
    gmail_read_at TEXT,
    notification_state TEXT NOT NULL DEFAULT 'not_queued'
        CHECK(notification_state IN ('not_queued', 'queued')),
    notification_queued_at TEXT,
    processed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_gmail_messages_thread_id ON gmail_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_gmail_messages_status ON gmail_messages(status);

CREATE TABLE IF NOT EXISTS notification_outbox (
    id INTEGER PRIMARY KEY,
    account_id TEXT NOT NULL,
    notification_kind TEXT NOT NULL CHECK(notification_kind IN ('immediate_alert', 'daily_summary')),
    message_id TEXT,
    importance TEXT CHECK(importance IN ('IMPORTANTE', 'NO_IMPORTANTE', 'REVISION')),
    category TEXT,
    priority TEXT,
    summary TEXT,
    scheduled_for TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'Europe/Madrid',
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'delivered', 'failed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, notification_kind, message_id, scheduled_for)
);

CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending
    ON notification_outbox(status, scheduled_for);
