PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    account_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processing_state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(account_id, message_id)
);

CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY,
    message_row_id INTEGER NOT NULL UNIQUE REFERENCES messages(id),
    category TEXT NOT NULL,
    priority TEXT NOT NULL CHECK(priority IN ('P0', 'P1', 'P2', 'P3')),
    label TEXT NOT NULL,
    summary TEXT NOT NULL,
    confidence REAL NOT NULL,
    injection_detected INTEGER NOT NULL DEFAULT 0,
    classified_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_labels (
    id INTEGER PRIMARY KEY,
    message_row_id INTEGER NOT NULL REFERENCES messages(id),
    label TEXT NOT NULL,
    UNIQUE(message_row_id, label)
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    message_row_id INTEGER NOT NULL REFERENCES messages(id),
    recipient TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('simulated_pending', 'simulated_recorded')),
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_row_id, recipient)
);
