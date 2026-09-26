import json
from pathlib import Path

from .classifier import classify
from .database import Database
from .schemas import Email

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    policy = json.loads((ROOT / "config" / "policy.json").read_text(encoding="utf-8"))
    emails = [Email(**item) for item in json.loads((ROOT / "fixtures" / "emails.json").read_text(encoding="utf-8"))]
    database = Database(ROOT / "data" / "mail-agent.sqlite3", ROOT / "db" / "schema.sql")
    try:
        for email in emails:
            database.process(email, classify(email), policy["notification"]["allowed_recipient"])
        rows = [dict(row) for row in database.report_rows()]
    finally:
        database.close()
    (ROOT / "reports" / "results.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Resultados locales", "", "| ID | Categoría | Prioridad | Inyección | Notificación |", "|---|---|---|---|---|"]
    lines.extend(f"| {r['message_id']} | {r['category']} | {r['priority']} | {'sí' if r['injection_detected'] else 'no'} | {r['notification_status'] or '—'} |" for r in rows)
    (ROOT / "reports" / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
