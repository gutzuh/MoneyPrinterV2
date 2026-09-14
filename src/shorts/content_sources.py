import datetime as dt
import hashlib
import json
import random
from pathlib import Path

import requests
from PIL import Image
from io import BytesIO

from .models import ContentTopic

WIKIPEDIA_API = "https://pt.wikipedia.org/w/api.php"
USER_AGENT = "MoneyPrinterV2/1.0 (automatic educational shorts)"

SEARCHES = {
    "tecnologia": [
        "história da computação", "invenções tecnológicas", "exploração espacial",
        "inteligência artificial", "internet", "segurança da informação",
    ],
    "curiosidade": [
        "fenômenos naturais", "animais", "corpo humano", "astronomia",
        "oceanos", "lugares incomuns",
    ],
}


def _get(params: dict) -> dict:
    response = requests.get(
        WIKIPEDIA_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30
    )
    response.raise_for_status()
    return response.json()


def _seen_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        return set()


def _remember(path: Path, topic_id: str, seen: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted((*seen, topic_id))[-500:], ensure_ascii=False), encoding="utf-8")


def _wikipedia_topic(category: str, rng: random.Random) -> ContentTopic:
    query = rng.choice(SEARCHES[category])
    search = _get({
        "action": "query", "list": "search", "srsearch": query,
        "srnamespace": 0, "srlimit": 20, "format": "json", "utf8": 1,
    })
    candidates = search["query"]["search"]
    selected = rng.choice(candidates)
    page_id = selected["pageid"]
    page = _get({
        "action": "query", "pageids": page_id, "prop": "extracts|info",
        "exintro": 1, "explaintext": 1, "inprop": "url", "format": "json",
    })["query"]["pages"][str(page_id)]
    return ContentTopic(category, page["title"], page.get("extract", "")[:5000], "Wikipédia", page["fullurl"])


def _history_topic(rng: random.Random) -> ContentTopic:
    today = dt.datetime.now(dt.timezone.utc)
    response = requests.get(
        f"https://pt.wikipedia.org/api/rest_v1/feed/onthisday/events/{today.month:02}/{today.day:02}",
        headers={"User-Agent": USER_AGENT}, timeout=30,
    )
    response.raise_for_status()
    event = rng.choice(response.json()["events"])
    pages = event.get("pages", [])
    url = pages[0].get("content_urls", {}).get("desktop", {}).get("page", "https://pt.wikipedia.org/") if pages else "https://pt.wikipedia.org/"
    return ContentTopic("historia", f"Neste dia, em {event['year']}", event["text"], "Wikimedia — Neste dia", url)


def _topic_id(topic: ContentTopic) -> str:
    return hashlib.sha256(f"{topic.category}:{topic.title}".encode()).hexdigest()[:20]


def mark_topic_seen(topic: ContentTopic, state_path: str) -> None:
    state = Path(state_path)
    _remember(state, _topic_id(topic), _seen_ids(state))


def collect_topic(categories: tuple[str, ...], state_path: str, seed: int | None = None, remember: bool = True) -> ContentTopic:
    allowed = [item for item in categories if item in {"historia", "tecnologia", "curiosidade"}]
    if not allowed:
        raise ValueError("auto_categories must contain historia, tecnologia or curiosidade")
    rng = random.Random(seed)
    state = Path(state_path)
    seen = _seen_ids(state)
    for _ in range(12):
        category = rng.choice(allowed)
        topic = _history_topic(rng) if category == "historia" else _wikipedia_topic(category, rng)
        topic_id = _topic_id(topic)
        if topic_id not in seen:
            if remember:
                _remember(state, topic_id, seen)
            return topic
    raise RuntimeError("Could not find an unused topic after 12 attempts")


def download_topic_images(topic: ContentTopic, output_dir: str, count: int = 4) -> list[str]:
    """Download freely hosted Wikimedia thumbnails related to the selected topic."""
    pages = []
    for namespace in (0, 6):
        api_url = WIKIPEDIA_API if namespace == 0 else "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query", "generator": "search", "gsrsearch": topic.title,
            "gsrnamespace": namespace, "gsrlimit": max(count + 2, 6),
            "prop": "pageimages|info" if namespace == 0 else "imageinfo",
            "piprop": "thumbnail" if namespace == 0 else None,
            "pithumbsize": 1080 if namespace == 0 else None,
            "iiprop": "url" if namespace == 6 else None,
            "iiurlwidth": 1080 if namespace == 6 else None,
            "format": "json", "formatversion": 2,
        }
        params = {key: value for key, value in params.items() if value is not None}
        response = requests.get(api_url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
        pages.extend(response.json().get("query", {}).get("pages", []))
        if len(pages) >= count:
            break
    paths: list[str] = []
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for index, page in enumerate(pages):
        imageinfo = page.get("imageinfo", [])
        image_url = page.get("thumbnail", {}).get("source")
        if imageinfo:
            image_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
        if not image_url:
            continue
        try:
            response = requests.get(image_url, headers={"User-Agent": USER_AGENT}, timeout=30)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGB")
            path = Path(output_dir) / f"image-{len(paths) + 1}.jpg"
            image.save(path, "JPEG", quality=92)
            paths.append(str(path))
        except (OSError, requests.RequestException):
            continue
        if len(paths) >= count:
            break
    return paths
