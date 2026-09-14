#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shorts.settings import load_settings
from shorts.youtube_api import authorize


if __name__ == "__main__":
    settings = load_settings(
        sys.argv[1] if len(sys.argv) > 1 else "config.json", require_groq=False
    )
    authorize(settings.youtube_client_secrets, settings.youtube_token_file)
    print(f"YouTube autorizado. Token salvo em {settings.youtube_token_file}")
