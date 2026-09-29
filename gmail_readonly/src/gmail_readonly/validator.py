"""Strict validation of mail_reader output; invalid values are never corrected."""
import json

from .types import MailReaderResult

CATEGORIES = {
    "Entrevista", "Recruiter", "Candidatura", "Vacante", "Rechazo", "Newsletter", "Administración", "Revisión",
}
PRIORITIES = {"P0", "P2", "P3"}
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
    if category not in CATEGORIES:
        raise ResponseValidationError("invalid_category")
    if priority not in PRIORITIES:
        raise ResponseValidationError("invalid_priority")
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
