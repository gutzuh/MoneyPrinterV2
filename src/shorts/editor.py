import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .models import MediaAsset, ShortPlan, Storyboard, TranscriptSegment, WordTiming


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


def _write_ass_subtitles(segments: list[TranscriptSegment], output_path: str) -> str:
    def timestamp(value: float) -> str:
        centiseconds = max(0, round(value * 100))
        hours, remainder = divmod(centiseconds, 360_000)
        minutes, remainder = divmod(remainder, 6_000)
        seconds, centis = divmod(remainder, 100)
        return f"{hours:d}:{minutes:02}:{seconds:02}.{centis:02}"

    def escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,104,&H00FFFFFF,&H000000FF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,8,1,2,70,70,300,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for segment in segments:
        lines.append(
            "Dialogue: 0,"
            f"{timestamp(segment.start)},{timestamp(segment.end)},Default,,0,0,0,,"
            f"{escape(segment.text.strip())}"
        )
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
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
    if shutil.which("fc-match"):
        match = subprocess.run(["fc-match", "-f", "%{file}", "DejaVu Sans:style=Bold"], capture_output=True, text=True)
        if match.returncode == 0 and match.stdout:
            candidates.insert(0, Path(match.stdout))
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


def render_original_short(
    card_path: str,
    narration_path: str,
    subtitles_path: str,
    output_path: str,
    images: list[str] | None = None,
) -> str:
    duration = media_duration(narration_path) + 0.35
    ass_path = str(Path(output_path).with_suffix(".ass"))
    segments = []
    blocks = Path(subtitles_path).read_text(encoding="utf-8").strip().split("\n\n")
    for block in blocks:
        lines = block.splitlines()
        if len(lines) >= 3 and "-->" in lines[1]:
            start_raw, end_raw = lines[1].split("-->")

            def seconds(value: str) -> float:
                hours, minutes, rest = value.strip().replace(",", ".").split(":")
                return int(hours) * 3600 + int(minutes) * 60 + float(rest)

            segments.append(TranscriptSegment(seconds(start_raw), seconds(end_raw), " ".join(lines[2:])))
    subtitle_filter = str(Path(_write_ass_subtitles(segments, ass_path)).resolve()).replace("'", "'\\''").replace(":", "\\:")
    visual_paths = [card_path, *(images or [])]
    visual_duration = duration / len(visual_paths)
    inputs = []
    video_parts = []
    for index, path in enumerate(visual_paths):
        # One source frame lets zoompan create exactly one animated segment.
        inputs += ["-loop", "1", "-framerate", "1", "-t", "1", "-i", path]
        frames = max(1, round(visual_duration * 30))
        video_parts.append(
            f"[{index}:v]scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,"
            f"zoompan=z='min(zoom+0.0008,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30,"
            "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.20:t=fill,setsar=1[v%02d]" % index
        )
    concat_inputs = "".join(f"[v{index:02d}]" for index in range(len(visual_paths)))
    filters = ";".join(video_parts) + ";" + concat_inputs + f"concat=n={len(visual_paths)}:v=1:a=0[base];"
    filters += f"[base]subtitles='{subtitle_filter}':force_style='Alignment=2,FontSize=76,Bold=1,PrimaryColour=&H00FFFFFF,"
    filters += "OutlineColour=&H00000000,BorderStyle=1,Outline=4,Shadow=1,MarginV=300'[v]"
    _run(["ffmpeg", "-y", *inputs, "-i", narration_path, "-filter_complex", filters,
          "-map", "[v]", "-map", f"{len(visual_paths)}:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac",
          "-b:a", "192k", "-t", f"{duration:.3f}", "-movflags", "+faststart", output_path])
    return output_path


def write_karaoke_ass(words: list[WordTiming], output_path: str, group_size: int = 3) -> str:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,82,&H00FFFFFF,&H0000D7FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,1,2,70,70,290,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def stamp(value: float) -> str:
        cs = max(0, round(value * 100)); hours, rest = divmod(cs, 360000); minutes, rest = divmod(rest, 6000); seconds, centis = divmod(rest, 100)
        return f"{hours}:{minutes:02}:{seconds:02}.{centis:02}"
    events = []
    for index in range(0, len(words), group_size):
        group = words[index:index + group_size]
        if not group:
            continue
        karaoke = " ".join(f"{{\\kf{max(1, round((item.end-item.start)*100))}}}{item.word}" for item in group)
        events.append(f"Dialogue: 0,{stamp(group[0].start)},{stamp(group[-1].end)},Default,,0,0,0,,{karaoke}")
    Path(output_path).write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_path


def render_dynamic_short(
    card_path: str,
    narration_path: str,
    output_path: str,
    board: Storyboard,
    assets: list[MediaAsset],
    background: MediaAsset | None,
    words: list[WordTiming],
) -> str:
    """Render normalized scene clips, then add narration and karaoke captions."""
    require_ffmpeg()
    output = Path(output_path)
    scene_dir = output.parent / "scenes"
    scene_dir.mkdir(parents=True, exist_ok=True)
    clips = []
    for index, (scene, asset) in enumerate(zip(board.scenes, assets)):
        duration = max(1.0, scene.end - scene.start)
        clip = scene_dir / f"scene-{index:02}.mp4"
        fade_out = max(0.0, duration - 0.22)
        base_filter = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
        fade = f",fade=t=in:st=0:d=0.18,fade=t=out:st={fade_out:.3f}:d=0.22"
        if asset.kind == "video" and asset.path:
            command = ["ffmpeg", "-y", "-stream_loop", "-1", "-ss", f"{(index * 7.31) % 45:.2f}", "-i", asset.path,
                       "-t", f"{duration:.3f}", "-vf", base_filter + ",drawbox=x=0:y=0:w=iw:h=ih:color=black@0.18:t=fill" + fade]
        elif asset.kind == "image" and asset.path and background and background.path:
            command = ["ffmpeg", "-y", "-stream_loop", "-1", "-ss", f"{(index * 5.17) % 35:.2f}", "-i", background.path,
                       "-loop", "1", "-i", asset.path, "-t", f"{duration:.3f}", "-filter_complex",
                       f"[0:v]{base_filter},boxblur=8:2,drawbox=x=0:y=0:w=iw:h=ih:color=black@0.30:t=fill[bg];"
                       "[1:v]scale=900:1080:force_original_aspect_ratio=decrease,pad=920:1100:10:10:black@0.6[fg];"
                       f"[bg][fg]overlay=(W-w)/2:250:shortest=1{fade}[v]", "-map", "[v]"]
        else:
            source = asset.path if asset.kind == "image" and asset.path else card_path
            frames = max(1, round(duration * 30))
            command = ["ffmpeg", "-y", "-loop", "1", "-framerate", "1", "-i", source, "-t", f"{duration:.3f}",
                       "-vf", f"scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,"
                       f"zoompan=z='if(eq(on,0),1.02,min(zoom+0.0012,1.13))':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=1080x1920:fps=30,"
                       "drawbox=x=0:y=0:w=iw:h=ih:color=black@0.20:t=fill" + fade]
        command += ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30", str(clip)]
        _run(command)
        clips.append(clip)
    concat_file = scene_dir / "concat.txt"
    concat_file.write_text("".join(f"file '{path.resolve()}'\n" for path in clips), encoding="utf-8")
    base_video = output.parent / "visuals.mp4"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(base_video)])
    captions = write_karaoke_ass(words, str(output.parent / "captions.ass"))
    subtitle_filter = str(Path(captions).resolve()).replace("'", "'\\''").replace(":", "\\:")
    duration = media_duration(narration_path)
    _run(["ffmpeg", "-y", "-i", str(base_video), "-i", narration_path,
          "-filter_complex", f"[0:v]subtitles='{subtitle_filter}'[v];[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=async=1:first_pts=0[a]",
          "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
          "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output)])
    return str(output)
