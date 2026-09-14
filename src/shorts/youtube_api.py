import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def authorize(client_secrets: str, token_file: str) -> Credentials:
    credentials = None
    token_path = Path(token_file)
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
        credentials = flow.run_local_server(port=0)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    token_path.chmod(0o600)
    return credentials


def upload_video(
    video_path: str,
    metadata_path: str,
    client_secrets: str,
    token_file: str,
    privacy: str = "private",
    publish_at: str | None = None,
) -> str:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    status = {"privacyStatus": "private" if publish_at else privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["publishAt"] = publish_at
    youtube = build("youtube", "v3", credentials=authorize(client_secrets, token_file))
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata.get("tags", []),
                "categoryId": "24",
            },
            "status": status,
        },
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return str(response["id"])
