import json
import re

import requests

from .models import ShortPlan, TranscriptSegment
from .settings import ShortsSettings


def _extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("Groq did not return a JSON object")
    return json.loads(match.group(0))


def plan_short(
    segments: list[TranscriptSegment], settings: ShortsSettings
) -> ShortPlan:
    transcript = "\n".join(
        f"[{item.start:.2f}-{item.end:.2f}] {item.text}" for item in segments
    )
    prompt = f"""Você é editor de YouTube Shorts em português brasileiro.
Escolha UM trecho contínuo e compreensível da transcrição, entre
{settings.min_duration} e {settings.max_duration} segundos. Crie uma narração
original que explique e comente a cena; não apenas repita as falas. Comece com
um gancho forte, entregue contexto e termine com uma observação curta. A
narração precisa caber naturalmente no trecho escolhido.

Retorne SOMENTE JSON válido neste formato:
{{"start": 12.3, "end": 50.1, "narration": "...", "title": "... #shorts",
"description": "...", "tags": ["family guy", "desenhos", "shorts"]}}

Não invente acontecimentos que não estejam na transcrição. Evite copiar falas
longas. Transcrição:
{transcript[:50000]}
"""
    response = requests.post(
        f"{settings.groq_base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
        },
        timeout=120,
    )
    response.raise_for_status()
    data = _extract_json(response.json()["choices"][0]["message"]["content"])
    plan = ShortPlan(
        start=float(data["start"]),
        end=float(data["end"]),
        narration=str(data["narration"]).strip(),
        title=str(data["title"]).strip()[:100],
        description=str(data["description"]).strip(),
        tags=[str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()],
    )
    if plan.start < 0 or plan.duration < settings.min_duration or plan.duration > settings.max_duration:
        raise ValueError(f"Groq selected an invalid duration: {plan.duration:.1f}s")
    return plan
