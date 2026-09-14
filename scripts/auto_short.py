#!/usr/bin/env python3
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from shorts.auto_content import create_original_plan
from shorts.content_sources import collect_topic
from shorts.editor import create_topic_card, render_original_short, write_metadata, write_srt
from shorts.settings import load_settings
from shorts.transcriber import transcribe
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
    args = parser.parse_args()
    settings = load_settings(args.config)
    categories = (args.category,) if args.category else settings.auto_categories
    print("[1/5] Coletando um assunto com fonte...")
    topic = collect_topic(categories, ".mp/seen_topics.json", args.seed)
    print(f"      {topic.category}: {topic.title}")
    print("[2/5] Criando roteiro original com Groq...")
    plan = create_original_plan(topic, settings)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    job = Path(settings.output_dir) / f"{stamp}-{slugify(plan.title)}"
    job.mkdir(parents=True)
    narration = synthesize(plan.narration, settings.tts_voice, str(job / "narration.mp3"), settings.tts_rate)
    print("[3/5] Gerando voz e legendas...")
    captions = write_srt(transcribe(narration, settings, words_per_caption=3), str(job / "captions.srt"))
    print("[4/5] Renderizando visual original...")
    card = create_topic_card(topic.title, topic.category, str(job / "card.jpg"))
    video = render_original_short(card, narration, captions, str(job / "short.mp4"))
    metadata = write_metadata(plan, str(job / "metadata.json"))
    result = {"video": video, "metadata": metadata, "source": topic.source_url, "uploaded": False}
    if args.upload:
        print("[5/5] Enviando ao YouTube...")
        result["youtube_id"] = upload_video(video, metadata, settings.youtube_client_secrets, settings.youtube_token_file, settings.youtube_privacy, args.publish_at)
        result["uploaded"] = True
    else:
        print("[5/5] Pronto para revisão; upload não solicitado.")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
