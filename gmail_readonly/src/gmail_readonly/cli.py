"""Explicit commands only; no import path polls Gmail automatically."""
import argparse
from pathlib import Path

from .gmail_client import GmailReadonlyClient
from .mail_reader_client import run_mail_reader
from .oauth import authorize, build_service
from .poller import process_message
from .store import Store

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
    process_parser = subparsers.add_parser("process")
    process_parser.add_argument("--account", required=True)
    process_parser.add_argument("--message-id", required=True)
    process_parser.add_argument("--client-secrets", type=Path, required=True)
    process_parser.add_argument("--token-path", type=Path, required=True)
    process_parser.add_argument("--database", type=Path, default=ROOT.parent / "data" / "gmail-readonly.sqlite3")
    args = parser.parse_args()
    credentials = authorize(args.client_secrets, args.token_path)
    client = GmailReadonlyClient(build_service(credentials), args.account)
    if args.command == "authorize":
        return
    if args.command == "list":
        for message_id in client.list_inbox_ids(args.max_results):
            print(message_id)
        return
    store = Store(args.database, SCHEMA)
    try:
        print(process_message(client.get_message(args.message_id), store, run_mail_reader))
    finally:
        store.close()


if __name__ == "__main__":
    main()
