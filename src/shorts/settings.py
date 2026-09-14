import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ShortsSettings:
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-20b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    tts_voice: str = "pt-BR-AntonioNeural"
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute_type: str = "int8"
    min_duration: int = 25
    max_duration: int = 48
    output_dir: str = ".mp/shorts"
    youtube_client_secrets: str = "client_secret.json"
    youtube_token_file: str = ".mp/youtube_token.json"
    youtube_privacy: str = "private"


def load_settings(config_path: str = "config.json", require_groq: bool = True) -> ShortsSettings:
    payload: dict = {}
    path = Path(config_path)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("shorts", {})
    if not isinstance(raw, dict):
        raise ValueError("The 'shorts' configuration must be an object")

    api_key = os.environ.get("GROQ_API_KEY", "").strip() or str(
        raw.get("groq_api_key", "")
    ).strip()
    if require_groq and not api_key:
        raise ValueError("Set GROQ_API_KEY before generating a short")

    def value(name: str, default):
        return raw.get(name, default)

    return ShortsSettings(
        groq_api_key=api_key,
        groq_model=str(value("groq_model", "openai/gpt-oss-20b")),
        groq_base_url=str(value("groq_base_url", "https://api.groq.com/openai/v1")),
        tts_voice=str(value("tts_voice", "pt-BR-AntonioNeural")),
        whisper_model=str(value("whisper_model", "small")),
        whisper_device=str(value("whisper_device", "auto")),
        whisper_compute_type=str(value("whisper_compute_type", "int8")),
        min_duration=int(value("min_duration", 25)),
        max_duration=int(value("max_duration", 48)),
        output_dir=str(value("output_dir", ".mp/shorts")),
        youtube_client_secrets=str(value("youtube_client_secrets", "client_secret.json")),
        youtube_token_file=str(value("youtube_token_file", ".mp/youtube_token.json")),
        youtube_privacy=str(value("youtube_privacy", "private")),
    )
