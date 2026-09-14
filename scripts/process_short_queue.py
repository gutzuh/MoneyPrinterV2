#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Process the next authorized video in input/")
    parser.add_argument("--input-dir", default="input")
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--all", action="store_true", help="Process every queued file")
    args = parser.parse_args()

    input_dir = (ROOT_DIR / args.input_dir).resolve()
    processed_dir = input_dir / "processed"
    failed_dir = input_dir / "failed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    candidates = sorted(
        path for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".mp4", ".mkv", ".mov", ".webm"}
    )
    if not candidates:
        print("Fila vazia.")
        return 0
    if not args.all:
        candidates = candidates[:1]

    failures = 0
    for source in candidates:
        command = [sys.executable, str(ROOT_DIR / "scripts" / "family_guy_short.py"), str(source)]
        if args.upload:
            command.append("--upload")
        result = subprocess.run(command, cwd=ROOT_DIR)
        destination = (processed_dir if result.returncode == 0 else failed_dir) / source.name
        source.replace(destination)
        if result.returncode != 0:
            failures += 1
            print(f"Falhou: {source.name}. Movido para {failed_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
