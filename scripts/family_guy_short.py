#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shorts.editor import fit_narration, render_short, write_metadata, write_srt
from shorts.groq_client import plan_short
from shorts.settings import load_settings
from shorts.transcriber import transcribe
from shorts.voice import synthesize
from shorts.youtube_api import upload_video


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value[:60] or "short"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a narrated vertical Short from an authorized local video."
    )
    parser.add_argument("source", help="Local video file you own or are authorized to reuse")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--upload", action="store_true", help="Upload after rendering")
    parser.add_argument("--publish-at", help="RFC3339 UTC timestamp, e.g. 2026-09-15T15:00:00Z")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_file():
        parser.error(f"source file not found: {source}")

    settings = load_settings(args.config)
    output_root = Path(settings.output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    print("[1/5] Transcrevendo o vídeo...")
    source_segments = transcribe(str(source), settings)
    if not source_segments:
        raise RuntimeError("No speech was detected in the source video")

    print("[2/5] Groq escolhendo a cena e escrevendo a narração...")
    plan = plan_short(source_segments, settings)
    job_dir = output_root / slugify(plan.title)
    suffix = 1
    while job_dir.exists():
        suffix += 1
        job_dir = output_root / f"{slugify(plan.title)}-{suffix}"
    job_dir.mkdir(parents=True)

    narration_path = job_dir / "narration.mp3"
    print("[3/5] Gerando voz em português...")
    synthesize(plan.narration, settings.tts_voice, str(narration_path), settings.tts_rate)
    fitted_narration = fit_narration(
        str(narration_path), plan.duration, str(job_dir / "narration-fit.mp3")
    )
    # Avoid a long silent tail when the generated narration is shorter than the scene.
    from shorts.editor import media_duration
    plan = type(plan)(plan.start, plan.start + min(plan.duration, media_duration(fitted_narration) + 0.5), plan.narration, plan.title, plan.description, plan.tags)

    print("[4/5] Criando legendas e renderizando 1080x1920...")
    narration_segments = transcribe(fitted_narration, settings, words_per_caption=3)
    subtitles_path = write_srt(narration_segments, str(job_dir / "captions.srt"))
    video_path = render_short(
        str(source), fitted_narration, subtitles_path, str(job_dir / "short.mp4"), plan
    )
    metadata_path = write_metadata(plan, str(job_dir / "metadata.json"))

    result = {"video": video_path, "metadata": metadata_path, "uploaded": False}
    if args.upload:
        print("[5/5] Enviando para o YouTube...")
        video_id = upload_video(
            video_path,
            metadata_path,
            settings.youtube_client_secrets,
            settings.youtube_token_file,
            settings.youtube_privacy,
            args.publish_at,
        )
        result.update({"uploaded": True, "youtube_id": video_id})
    else:
        print("[5/5] Upload não solicitado; revise o vídeo antes de publicar.")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
