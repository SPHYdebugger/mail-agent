"""OAuth is opt-in: importing this module performs no network access."""
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def authorize(client_secrets: Path, token_path: Path):
    """Run desktop OAuth only when the caller explicitly invokes this function."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
            credentials = flow.run_local_server(
                host="127.0.0.1",
                port=8765,
                open_browser=False,
            )
        token_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")
        token_path.chmod(0o600)
    return credentials


def build_service(credentials):
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)
