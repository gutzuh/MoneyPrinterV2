import hashlib
import html
import json
import os
import random
import re
from pathlib import Path

import requests

from .models import ContentTopic, MediaAsset, Storyboard
from .settings import ShortsSettings

USER_AGENT = "MoneyPrinterV2/2.0 (automatic sourced shorts)"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


def _download(url: str, cache: Path, extension: str) -> str:
    path = cache / f"{hashlib.sha256(url.encode()).hexdigest()}{extension}"
    if path.exists() and path.stat().st_size > 4096:
        return str(path)
    cache.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".part")
    with requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=(10, 60)) as response:
        response.raise_for_status()
        total = 0
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(1024 * 256):
                total += len(chunk)
                if total > 120 * 1024 * 1024:
                    raise ValueError("asset exceeds 120 MB")
                handle.write(chunk)
    temporary.replace(path)
    return str(path)


def _local_backgrounds(settings: ShortsSettings) -> list[MediaAsset]:
    root = Path(settings.local_backgrounds_dir)
    if not root.exists():
        return []
    return [MediaAsset(str(path), "video", "local", "", "", "owned-or-user-approved", "satisfying")
            for path in root.rglob("*") if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS]


def _wikimedia(query: str, settings: ShortsSettings) -> MediaAsset | None:
    params = {"action": "query", "generator": "search", "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 1400,
        "format": "json", "formatversion": 2}
    response = requests.get("https://commons.wikimedia.org/w/api.php", params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()
    for page in response.json().get("query", {}).get("pages", []):
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime", "") not in {"image/jpeg", "image/png", "image/webp"} or min(info.get("width", 0), info.get("height", 0)) < 480:
            continue
        metadata = info.get("extmetadata", {})
        license_name = metadata.get("LicenseShortName", {}).get("value", "")
        if not any(token in license_name.lower() for token in ("cc0", "public domain", "cc by")):
            continue
        url = info.get("thumburl") or info.get("url")
        if url:
            author = html.unescape(re.sub(r"<[^>]+>", "", metadata.get("Artist", {}).get("value", ""))).strip()
            return MediaAsset(_download(url, Path(settings.media_cache_dir), ".jpg"), "image", "wikimedia",
                info.get("descriptionurl", ""), author, license_name, query)
    return None


def _pexels(query: str, kind: str, settings: ShortsSettings) -> MediaAsset | None:
    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        return None
    headers = {"Authorization": key}
    if kind == "video":
        response = requests.get("https://api.pexels.com/videos/search", params={"query": query, "orientation": "portrait", "per_page": 8}, headers=headers, timeout=30)
        response.raise_for_status()
        for video in response.json().get("videos", []):
            files = sorted(video.get("video_files", []), key=lambda item: abs(item.get("height", 0) - 1920))
            for item in files:
                if item.get("file_type") == "video/mp4" and item.get("height", 0) >= 720:
                    return MediaAsset(_download(item["link"], Path(settings.media_cache_dir), ".mp4"), "video", "pexels",
                        video.get("url", ""), video.get("user", {}).get("name", ""), "Pexels License", query)
    else:
        response = requests.get("https://api.pexels.com/v1/search", params={"query": query, "orientation": "portrait", "per_page": 8}, headers=headers, timeout=30)
        response.raise_for_status()
        photos = response.json().get("photos", [])
        if photos:
            photo = photos[0]
            return MediaAsset(_download(photo["src"]["large2x"], Path(settings.media_cache_dir), ".jpg"), "image", "pexels",
                photo.get("url", ""), photo.get("photographer", ""), "Pexels License", query)
    return None


def resolve_assets(board: Storyboard, topic: ContentTopic, settings: ShortsSettings, provider: str = "auto") -> tuple[list[MediaAsset], MediaAsset | None]:
    backgrounds = _local_backgrounds(settings)
    background = random.choice(backgrounds) if backgrounds else None
    assets, used = [], set()
    for scene in board.scenes:
        asset = background if scene.visual_type == "satisfying" and background else None
        if not asset and provider in {"auto", "pexels"}:
            try:
                asset = _pexels(scene.query_en, "video" if scene.visual_type == "related_video" else "image", settings)
            except requests.RequestException:
                asset = None
        if not asset and provider in {"auto", "wikimedia"}:
            try:
                asset = _wikimedia(scene.query_en or scene.query_pt, settings)
            except requests.RequestException:
                asset = None
        if asset and asset.path in used and asset is not background:
            asset = None
        asset = asset or background or MediaAsset("", "procedural", "generated", "", "", "original", scene.query_en)
        used.add(asset.path)
        assets.append(asset)
    return assets, background


def write_media_manifest(assets: list[MediaAsset], output_path: str) -> str:
    Path(output_path).write_text(json.dumps({"assets": [asset.__dict__ for asset in assets]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output_path


def attribution_text(assets: list[MediaAsset]) -> str:
    unique, lines = set(), []
    for asset in assets:
        key = (asset.provider, asset.source_url)
        if asset.source_url and key not in unique:
            unique.add(key)
            lines.append(f"• {asset.provider}: {asset.author or 'autor na fonte'} — {asset.license_name}: {asset.source_url}")
    return "\n".join(lines)
