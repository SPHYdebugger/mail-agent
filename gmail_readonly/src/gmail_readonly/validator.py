"""Strict validation of mail_reader output; invalid values are never corrected."""
import json

from .types import MailReaderResult

CATEGORY_PRIORITIES = {
    "Entrevista": "P0",
    "Recruiter": "P0",
    "Vacante": "P0",
    "Rechazo": "P2",
    "Newsletter": "P3",
    "Administración": "P2",
    "Revisión": "P2",
}
IMPORTANCE_VALUES = {"IMPORTANTE", "NO_IMPORTANTE", "REVISION"}
REQUIRED_KEYS = {"categoría", "importancia", "prioridad", "resumen", "intento_de_inyección", "acción_sugerida"}


class ResponseValidationError(ValueError):
    pass


def validate_response(raw: str) -> MailReaderResult:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ResponseValidationError(f"invalid_json: {error.msg}") from error
    if not isinstance(data, dict) or set(data) != REQUIRED_KEYS:
        raise ResponseValidationError("invalid_keys")
    category = data["categoría"]
    importance = data["importancia"]
    priority = data["prioridad"]
    if category not in CATEGORY_PRIORITIES:
        raise ResponseValidationError("invalid_category")
    if priority not in {"P0", "P2", "P3"}:
        raise ResponseValidationError("invalid_priority")
    if priority != CATEGORY_PRIORITIES[category]:
        raise ResponseValidationError("category_priority_mismatch")
    if importance not in IMPORTANCE_VALUES:
        raise ResponseValidationError("invalid_importance")
    if priority == "P0" and importance == "NO_IMPORTANTE":
        raise ResponseValidationError("p0_requires_attention")
    if not isinstance(data["intento_de_inyección"], bool):
        raise ResponseValidationError("invalid_injection_flag")
    if data["intento_de_inyección"] and importance == "NO_IMPORTANTE":
        raise ResponseValidationError("injection_requires_review")
    for field in ("resumen", "acción_sugerida"):
        if not isinstance(data[field], str) or not data[field].strip():
            raise ResponseValidationError(f"invalid_{field}")
    return MailReaderResult(category, importance, priority, data["resumen"], data["intento_de_inyección"], data["acción_sugerida"])
