"""Safe extraction of text bodies; attachments are always ignored."""
import base64
import html
import re


def _decode(data: str) -> str:
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    return raw.decode("utf-8", errors="replace")


def _strip_html(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def extract_text(payload: dict, max_chars: int = 20_000) -> str:
    """Return text/plain first, then safe text from HTML; never return attachments."""
    plain: list[str] = []
    html_parts: list[str] = []

    def visit(part: dict) -> None:
        if part.get("filename") or part.get("body", {}).get("attachmentId"):
            return
        mime_type = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data and mime_type == "text/plain":
            plain.append(_decode(data))
        elif data and mime_type == "text/html":
            html_parts.append(_strip_html(_decode(data)))
        for child in part.get("parts", []):
            visit(child)

    visit(payload)
    text = "\n".join(plain) if plain else "\n".join(html_parts)
    return text[:max_chars]
