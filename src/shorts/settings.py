import json
import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without adding a runtime dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


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
    auto_categories: tuple[str, ...] = ("historia", "tecnologia", "curiosidade")
    auto_target_duration: int = 32
    tts_rate: str = "+8%"
    media_cache_dir: str = ".mp/asset-cache"
    local_backgrounds_dir: str = "assets/backgrounds"
    media_providers: tuple[str, ...] = ("local", "wikimedia", "pexels")
    caption_highlight_color: str = "&H0000D7FF"

    def __post_init__(self) -> None:
        if not 15 <= self.min_duration < self.max_duration <= 60:
            raise ValueError("short duration range must be between 15 and 60 seconds")
        if self.youtube_privacy not in {"private", "unlisted", "public"}:
            raise ValueError("youtube_privacy must be private, unlisted or public")
        allowed = {"historia", "tecnologia", "curiosidade"}
        if not self.auto_categories or not set(self.auto_categories) <= allowed:
            raise ValueError("invalid auto_categories")


def load_settings(config_path: str = "config.json", require_groq: bool = True) -> ShortsSettings:
    _load_dotenv(Path(config_path).resolve().parent / ".env")
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
    if api_key == "REPLACE_WITH_YOUR_GROQ_API_KEY":
        api_key = ""
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
        auto_categories=tuple(value("auto_categories", ["historia", "tecnologia", "curiosidade"])),
        auto_target_duration=int(value("auto_target_duration", 32)),
        tts_rate=str(value("tts_rate", "+8%")),
        media_cache_dir=str(value("media_cache_dir", ".mp/asset-cache")),
        local_backgrounds_dir=str(value("local_backgrounds_dir", "assets/backgrounds")),
        media_providers=tuple(value("media_providers", ["local", "wikimedia", "pexels"])),
        caption_highlight_color=str(value("caption_highlight_color", "&H0000D7FF")),
    )
