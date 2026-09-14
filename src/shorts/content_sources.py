import datetime as dt
import hashlib
import json
import random
from pathlib import Path

import requests

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


def collect_topic(categories: tuple[str, ...], state_path: str, seed: int | None = None) -> ContentTopic:
    allowed = [item for item in categories if item in {"historia", "tecnologia", "curiosidade"}]
    if not allowed:
        raise ValueError("auto_categories must contain historia, tecnologia or curiosidade")
    rng = random.Random(seed)
    state = Path(state_path)
    seen = _seen_ids(state)
    for _ in range(12):
        category = rng.choice(allowed)
        topic = _history_topic(rng) if category == "historia" else _wikipedia_topic(category, rng)
        topic_id = hashlib.sha256(f"{topic.category}:{topic.title}".encode()).hexdigest()[:20]
        if topic_id not in seen:
            _remember(state, topic_id, seen)
            return topic
    raise RuntimeError("Could not find an unused topic after 12 attempts")
