"""Explicit commands only; no import path polls Gmail automatically."""
import argparse
import json
from pathlib import Path

from .gmail_client import GmailReadonlyClient
from .gmail_mutation_guard import GmailReadStateGuard
from .gmail_organization_guard import GmailOrganizationGuard, ensure_organization_labels
from .mail_reader_client import run_mail_reader
from .oauth import authorize, build_service
from .poller import poll_once, process_message
from .read_state import apply_processed_read_state
from .store import Store
from .telegram_sender import TelegramSender, send_pending_notifications
from .summary_sender import send_summary_once

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "db" / "gmail_schema.sql"


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    authorize_parser = subparsers.add_parser("authorize")
    authorize_parser.add_argument("--client-secrets", type=Path, required=True)
    authorize_parser.add_argument("--token-path", type=Path, required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--account", required=True)
    list_parser.add_argument("--client-secrets", type=Path, required=True)
    list_parser.add_argument("--token-path", type=Path, required=True)
    list_parser.add_argument("--max-results", type=int, default=1)
    metadata_parser = subparsers.add_parser("metadata")
    metadata_parser.add_argument("--account", required=True)
    metadata_parser.add_argument("--message-id", required=True)
    metadata_parser.add_argument("--client-secrets", type=Path, required=True)
    metadata_parser.add_argument("--token-path", type=Path, required=True)
    apply_parser = subparsers.add_parser("apply-read-state")
    apply_parser.add_argument("--account", required=True)
    apply_parser.add_argument("--message-id", required=True)
    apply_parser.add_argument("--client-secrets", type=Path, required=True)
    apply_parser.add_argument("--token-path", type=Path, required=True)
    apply_parser.add_argument("--database", type=Path, default=ROOT.parent / "data" / "gmail-readonly.sqlite3")
    poll_parser = subparsers.add_parser("poll-once")
    poll_parser.add_argument("--account", required=True)
    poll_parser.add_argument("--client-secrets", type=Path, required=True)
    poll_parser.add_argument("--token-path", type=Path, required=True)
    poll_parser.add_argument("--database", type=Path, default=ROOT.parent / "data" / "gmail-readonly.sqlite3")
    poll_parser.add_argument("--max-results", type=int, default=25)
    send_parser = subparsers.add_parser("send-notifications-once")
    send_parser.add_argument("--database", type=Path, default=ROOT.parent / "data" / "gmail-readonly.sqlite3")
    summary_parser = subparsers.add_parser("send-summary-once")
    summary_parser.add_argument("--account", required=True)
    summary_parser.add_argument("--database", type=Path, default=ROOT.parent / "data" / "gmail-readonly.sqlite3")
    process_parser = subparsers.add_parser("process")
    process_parser.add_argument("--account", required=True)
    process_parser.add_argument("--message-id", required=True)
    process_parser.add_argument("--client-secrets", type=Path, required=True)
    process_parser.add_argument("--token-path", type=Path, required=True)
    process_parser.add_argument("--database", type=Path, default=ROOT.parent / "data" / "gmail-readonly.sqlite3")
    args = parser.parse_args()
    if args.command == "send-notifications-once":
        store=Store(args.database, SCHEMA)
        try: print(json.dumps(send_pending_notifications(store, TelegramSender())))
        finally: store.close()
        return
    if args.command == "send-summary-once":
        store=Store(args.database, SCHEMA)
        try: print(json.dumps(send_summary_once(store, TelegramSender(), args.account)))
        finally: store.close()
        return
    if args.command == "apply-read-state":
        store = Store(args.database, SCHEMA)
        try:
            def gmail_components():
                credentials = authorize(args.client_secrets, args.token_path)
                service = build_service(credentials)
                return GmailReadonlyClient(service, args.account), GmailReadStateGuard(service)

            print(apply_processed_read_state(args.account, args.message_id, store, gmail_components))
        finally:
            store.close()
        return
    credentials = authorize(args.client_secrets, args.token_path)
    service = build_service(credentials)
    client = GmailReadonlyClient(service, args.account)
    if args.command == "authorize":
        return
    if args.command == "list":
        for message_id in client.list_inbox_ids(args.max_results):
            print(message_id)
        return
    if args.command == "metadata":
        print(json.dumps(client.get_metadata(args.message_id), ensure_ascii=False))
        return
    if args.command == "poll-once":
        store = Store(args.database, SCHEMA)
        try:
            labels = ensure_organization_labels(service)
            print(json.dumps(poll_once(client, store, run_mail_reader, GmailReadStateGuard(service), args.max_results, GmailOrganizationGuard(service, labels))))
        finally:
            store.close()
        return
    store = Store(args.database, SCHEMA)
    try:
        gmail_guard = GmailReadStateGuard(service)
        print(process_message(client.get_message(args.message_id), store, run_mail_reader, gmail_guard))
    finally:
        store.close()


if __name__ == "__main__":
    main()
