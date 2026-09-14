import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import ShortPlan, TranscriptSegment


def _run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def require_ffmpeg() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"Missing required command(s): {', '.join(missing)}")


def media_duration(media_path: str) -> float:
    require_ffmpeg()
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", media_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


def fit_narration(narration_path: str, target_duration: float, output_path: str) -> str:
    """Speed up narration only when necessary so it is never cut mid-sentence."""
    duration = media_duration(narration_path)
    if duration <= target_duration * 0.97:
        return narration_path
    speed = min(duration / (target_duration * 0.94), 2.0)
    if speed >= 2.0:
        raise ValueError("Narration is much too long for the selected clip")
    _run([
        "ffmpeg", "-y", "-i", narration_path, "-filter:a", f"atempo={speed:.5f}",
        "-vn", output_path,
    ])
    return output_path


def write_srt(segments: list[TranscriptSegment], output_path: str) -> str:
    def timestamp(value: float) -> str:
        milliseconds = max(0, round(value * 1000))
        hours, remainder = divmod(milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        seconds, millis = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"

    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n{timestamp(segment.start)} --> {timestamp(segment.end)}\n"
            f"{segment.text.strip()}"
        )
    Path(output_path).write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    return output_path


def render_short(
    source_path: str,
    narration_path: str,
    subtitles_path: str,
    output_path: str,
    plan: ShortPlan,
) -> str:
    require_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    subtitle_filter = str(Path(subtitles_path).resolve()).replace("'", "'\\''").replace(":", "\\:")
    video_filter = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,fps=30,"
        f"subtitles='{subtitle_filter}':force_style='Alignment=2,FontSize=28,"
        "Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "BorderStyle=1,Outline=3,Shadow=1,MarginV=170'[v];"
        "[0:a]volume=0.12[original];[1:a]volume=1.0[narration];"
        "[original][narration]amix=inputs=2:duration=first:dropout_transition=2[a]"
    )
    _run([
        "ffmpeg", "-y", "-ss", f"{plan.start:.3f}", "-t", f"{plan.duration:.3f}",
        "-i", source_path, "-i", narration_path, "-filter_complex", video_filter,
        "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium",
        "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-t", f"{plan.duration:.3f}", output_path,
    ])
    return output_path


def write_metadata(plan: ShortPlan, output_path: str) -> str:
    Path(output_path).write_text(
        json.dumps(
            {
                "title": plan.title,
                "description": plan.description,
                "tags": plan.tags,
                "source_start": plan.start,
                "source_end": plan.end,
                "narration": plan.narration,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return output_path


def create_topic_card(title: str, category: str, output_path: str) -> str:
    palettes = {"historia": (46, 27, 75), "tecnologia": (5, 55, 82), "curiosidade": (17, 73, 55)}
    base = palettes.get(category, (35, 35, 45))
    image = Image.new("RGB", (1080, 1920), base)
    draw = ImageDraw.Draw(image)
    for y in range(1920):
        factor = y / 1920
        color = tuple(max(0, int(value * (1 - factor * .55))) for value in base)
        draw.line((0, y, 1080, y), fill=color)
    candidates = [
        Path("/run/current-system/sw/share/fonts/truetype/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    font_path = next((path for path in candidates if path.exists()), None)
    font = ImageFont.truetype(str(font_path), 84) if font_path else ImageFont.load_default()
    label_font = ImageFont.truetype(str(font_path), 40) if font_path else ImageFont.load_default()
    words, lines, current = title.upper().split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] > 880 and current:
            lines.append(current); current = word
        else:
            current = candidate
    if current: lines.append(current)
    y = 520
    draw.rounded_rectangle((70, 130, 440, 210), 25, fill=(255, 255, 255))
    draw.text((100, 145), category.upper(), font=label_font, fill=base)
    for line in lines[:5]:
        draw.text((90, y), line, font=font, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
        y += 110
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, quality=95)
    return output_path


def render_original_short(card_path: str, narration_path: str, subtitles_path: str, output_path: str) -> str:
    duration = media_duration(narration_path) + 0.35
    subtitle_filter = str(Path(subtitles_path).resolve()).replace("'", "'\\''").replace(":", "\\:")
    filters = (
        "[0:v]scale=1200:2134,zoompan=z='min(zoom+0.0007,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={max(1, round(duration * 30))}:s=1080x1920:fps=30,"
        f"subtitles='{subtitle_filter}':force_style='Alignment=2,FontSize=20,Bold=1,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,MarginV=210'[v]"
    )
    _run(["ffmpeg", "-y", "-loop", "1", "-i", card_path, "-i", narration_path, "-filter_complex", filters,
          "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac",
          "-b:a", "192k", "-t", f"{duration:.3f}", "-movflags", "+faststart", output_path])
    return output_path
