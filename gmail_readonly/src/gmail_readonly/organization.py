"""Deterministic local routing; mail_reader never supplies Gmail label IDs."""
from .types import GmailMessage, MailReaderResult

TARGET_LABELS = {
    "no_importantes": "No importantes",
    "employment_single": "Empleo - Vacantes plataformas",
    "employment_aggregate": "Empleo - Agrupados plataformas",
    "platform_social": "Plataformas - Social",
    "general_newsletter": "General - Newsletters",
}
PLATFORMS = ("linkedin", "indeed", "jobalert", "jobleads")
AGGREGATE = ("empleos similares", "vacantes nuevas", "nuevas vacantes", "digest", "recopil", "recomendacion", "más de", "varias vacantes")
SOCIAL = ("podrías conocer", "conoces a", "ha publicado", "invitaciones", "visitas al perfil", "actividad de red", "tendencias")

def determine_organization_target(result: MailReaderResult, message: GmailMessage):
    if result.importance != "NO_IMPORTANTE" or result.injection_detected:
        return None
    text = f"{message.sender} {message.subject} {message.body}".lower()
    platform = any(word in text for word in PLATFORMS)
    if result.category == "Vacante":
        return "employment_aggregate" if any(word in text for word in AGGREGATE) else "employment_single"
    if platform and any(word in text for word in SOCIAL):
        return "platform_social"
    if result.category == "Newsletter":
        if any(word in text for word in ("indeed", "jobalert", "jobleads")):
            return "employment_aggregate"
        return "platform_social" if "linkedin" in text else "general_newsletter"
    return None
