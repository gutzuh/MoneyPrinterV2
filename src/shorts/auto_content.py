import json
import re

import requests

from .models import ContentTopic, ShortPlan
from .settings import ShortsSettings


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Groq did not return JSON")
    return json.loads(match.group(0))


def create_original_plan(topic: ContentTopic, settings: ShortsSettings) -> ShortPlan:
    target = settings.auto_target_duration
    minimum_words = round(target * 2.0)
    maximum_words = round(target * 2.35)
    prompt = f"""Crie um YouTube Short original em português brasileiro usando SOMENTE os fatos abaixo.
Categoria: {topic.category}. Assunto: {topic.title}.
Fatos da fonte: {topic.facts}

Escreva narração entre {minimum_words} e {maximum_words} palavras, para cerca de {target} segundos.
Estrutura: gancho imediato, explicação clara, surpresa/punchline e pergunta final curta.
Não diga que algo é atual se os fatos não disserem isso. Não copie frases longas da fonte.
Retorne apenas JSON: {{"narration":"...","title":"... #shorts","description":"...","tags":["..."]}}.
A descrição deve terminar com: Fonte: {topic.source_url}
"""
    last_error = None
    for _ in range(3):
        response = requests.post(
            f"{settings.groq_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json={"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.65, "response_format": {"type": "json_object"}},
            timeout=120,
        )
        response.raise_for_status()
        data = _extract_json(response.json()["choices"][0]["message"]["content"])
        narration = str(data["narration"]).strip()
        count = len(narration.split())
        if minimum_words <= count <= maximum_words + 8:
            return ShortPlan(0, float(target), narration, str(data["title"])[:100], str(data["description"]), [str(x) for x in data.get("tags", [])][:12])
        last_error = ValueError(f"Groq returned {count} words; expected {minimum_words}-{maximum_words}")
        prompt += f"\nA tentativa anterior teve {count} palavras. Respeite rigorosamente a faixa."
    raise last_error or RuntimeError("Groq failed to create a script")
