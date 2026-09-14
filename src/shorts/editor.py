import json
import shutil
import subprocess
from pathlib import Path

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
