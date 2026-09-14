#!/usr/bin/env python3
import argparse
import json
import re
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from shorts.auto_content import align_storyboard, create_storyboard
from shorts.content_sources import collect_topic, mark_topic_seen
from shorts.editor import create_topic_card, media_duration, render_dynamic_short, write_metadata
from shorts.media import attribution_text, resolve_assets, write_media_manifest
from shorts.quality import inspect_video, write_quality_report
from shorts.settings import load_settings
from shorts.transcriber import transcribe_words
from shorts.voice import synthesize
from shorts.youtube_api import upload_video


def slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()[:55] or "short"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate an original Short with no source video")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--category", choices=["historia", "tecnologia", "curiosidade"])
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--publish-at", help="RFC3339 UTC timestamp")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--visual-provider", choices=["auto", "local", "wikimedia", "pexels"], default="auto")
    parser.add_argument("--background", choices=["auto", "satisfying"], default="auto")
    parser.add_argument("--preview", action="store_true", help="Render without uploading")
    parser.add_argument("--dry-run", action="store_true", help="Create the storyboard without media or rendering")
    args = parser.parse_args()
    settings = load_settings(args.config)
    categories = (args.category,) if args.category else settings.auto_categories
    print("[1/5] Coletando um assunto com fonte...")
    state_path = ".mp/seen_topics.json"
    topic = collect_topic(categories, state_path, args.seed, remember=False)
    print(f"      {topic.category}: {topic.title}")
    print("[2/5] Criando roteiro original com Groq...")
    board = create_storyboard(topic, settings)
    plan = board.plan
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job = Path(settings.output_dir) / f"{stamp}-{slugify(plan.title)}"
    job.mkdir(parents=True)
    (job / "storyboard.json").write_text(json.dumps(asdict(board), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.dry_run:
        print(json.dumps({"storyboard": str(job / "storyboard.json"), "source": topic.source_url}, ensure_ascii=False, indent=2))
        return 0
    narration = synthesize(plan.narration, settings.tts_voice, str(job / "narration.mp3"), settings.tts_rate)
    print("[3/5] Gerando voz e legendas...")
    words = transcribe_words(narration, settings)
    board = align_storyboard(board, media_duration(narration))
    (job / "storyboard.json").write_text(json.dumps(asdict(board), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("[4/5] Renderizando visual original...")
    card = create_topic_card(topic.title, topic.category, str(job / "card.jpg"))
    assets, background = resolve_assets(board, topic, settings, args.visual_provider)
    write_media_manifest(assets, str(job / "media_manifest.json"))
    video = render_dynamic_short(card, narration, str(job / "short.mp4"), board, assets, background, words)
    credits = attribution_text(assets)
    plan = replace(board.plan, description=board.plan.description + (f"\n\nMídia e créditos:\n{credits}" if credits else ""))
    metadata = write_metadata(plan, str(job / "metadata.json"))
    report = inspect_video(video, narration, len(board.scenes))
    write_quality_report(report, str(job / "quality_report.json"))
    if not report["passed"]:
        raise RuntimeError(f"Quality validation failed: {report['checks']}")
    mark_topic_seen(topic, state_path)
    result = {"video": video, "metadata": metadata, "source": topic.source_url, "uploaded": False}
    if args.upload and not args.preview:
        print("[5/5] Enviando ao YouTube...")
        result["youtube_id"] = upload_video(video, metadata, settings.youtube_client_secrets, settings.youtube_token_file, settings.youtube_privacy, args.publish_at)
        result["uploaded"] = True
    else:
        print("[5/5] Pronto para revisão; upload não solicitado.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
