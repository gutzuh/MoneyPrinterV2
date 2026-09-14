import json
import subprocess
from pathlib import Path


def inspect_video(video_path: str, narration_path: str, scene_count: int) -> dict:
    def probe(path: str) -> dict:
        result = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path], check=True, capture_output=True, text=True)
        return json.loads(result.stdout)
    video, audio = probe(video_path), probe(narration_path)
    vstream = next((s for s in video["streams"] if s.get("codec_type") == "video"), {})
    astream = next((s for s in video["streams"] if s.get("codec_type") == "audio"), {})
    video_duration, narration_duration = float(video["format"]["duration"]), float(audio["format"]["duration"])
    checks = {"resolution_1080x1920": (vstream.get("width"), vstream.get("height")) == (1080, 1920),
        "video_h264": vstream.get("codec_name") == "h264", "pixel_format": vstream.get("pix_fmt") in {"yuv420p", "yuvj420p"},
        "audio_aac": astream.get("codec_name") == "aac", "duration_matches_narration": abs(video_duration - narration_duration) <= 0.5,
        "enough_scenes": scene_count >= 6, "file_size": Path(video_path).stat().st_size > 100_000}
    return {"passed": all(checks.values()), "checks": checks, "video_duration": video_duration,
            "narration_duration": narration_duration, "scene_count": scene_count}


def write_quality_report(report: dict, output_path: str) -> str:
    Path(output_path).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return output_path
