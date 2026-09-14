#!/usr/bin/env python3
import importlib.util
import os
import shutil
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    failures = 0
    for command in ("ffmpeg", "ffprobe"):
        path = shutil.which(command)
        if path:
            print(f"[OK] {command}: {path}")
        else:
            print(f"[FAIL] {command} não encontrado")
            failures += 1

    for module in ("faster_whisper", "edge_tts", "googleapiclient", "google_auth_oauthlib"):
        if importlib.util.find_spec(module):
            print(f"[OK] Python: {module}")
        else:
            print(f"[FAIL] Pacote Python ausente: {module}")
            failures += 1

    if os.environ.get("GROQ_API_KEY", "").strip():
        print("[OK] GROQ_API_KEY definida")
    else:
        print("[FAIL] GROQ_API_KEY não definida")
        failures += 1

    if (ROOT_DIR / "client_secret.json").exists():
        print("[OK] client_secret.json encontrado")
    else:
        print("[WARN] client_secret.json ausente; geração funciona, upload não")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
