"""Pure, deterministic classification. Email text is never executed or interpreted as policy."""
import re
from pathlib import Path
import json

from .schemas import Classification, Email

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = json.loads((ROOT / "config" / "categories.json").read_text(encoding="utf-8"))["categories"]

INJECTION_MARKERS = (
    "ignora tus instrucciones anteriores", "ignore previous instructions",
    "ejecuta este comando", "execute this command", "envía este correo",
    "send this email", "cambia el destinatario", "change the recipient",
    "policy.json", "categories.json", "agents.md", "reglas de prioridad",
    "destinatarios futuros de notificaciones"
)

RULES = (
    ("interview", ("entrevista", "interview", "technical interview")),
    ("recruiter", ("recruiter", "talent acquisition", "headhunter")),
    ("job_opening", ("oferta de trabajo", "job opening", "position available", "vacante")),
    ("application_rejection", ("otros candidatos", "not moving forward", "regret to inform", "no continuar")),
    ("newsletter", ("newsletter", "weekly digest", "weekly engineering")),
    ("administration", ("factura", "invoice", "billing")),
    ("work_action", ("acción requerida", "action required", "deadline")),
    ("work_information", ("actualización", "update", "información")),
)


def classify(email: Email) -> Classification:
    text = f"{email.subject} {email.body}".lower()
    category = next((name for name, markers in RULES if any(marker in text for marker in markers)), "review")
    data = CATEGORIES[category]
    injection = any(marker in text for marker in INJECTION_MARKERS)
    summary_text = re.sub(r"\s+", " ", email.body).strip()
    summary = f"De: {email.sender}. {summary_text[:180]}"
    return Classification(
        category=category,
        priority=data["priority"],
        label=f"{CATEGORIES and 'MailAgent'}/{data['label']}",
        summary=summary,
        confidence=1.0 if category != "review" else 0.4,
        injection_detected=injection,
        should_notify=bool(data["notify"]),
    )
