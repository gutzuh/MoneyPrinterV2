import json
import re
from dataclasses import replace

import requests

from .models import ContentTopic, ShortPlan, Storyboard, StoryboardScene
from .settings import ShortsSettings

VISUAL_TYPES = {"related_image", "related_video", "satisfying"}


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("Groq did not return JSON")
    return json.loads(match.group(0))


def create_storyboard(topic: ContentTopic, settings: ShortsSettings) -> Storyboard:
    target = settings.auto_target_duration
    minimum_words, maximum_words = round(target * 2.0), round(target * 2.35)
    prompt = f"""Crie um Short factual em português brasileiro usando SOMENTE os fatos abaixo.
Categoria: {topic.category}. Assunto: {topic.title}. Fatos: {topic.facts}
Narração: {minimum_words}-{maximum_words} palavras. Gancho específico nos primeiros 2 segundos, promessa clara,
escalada, payoff e pergunta final útil. Proibido começar com 'você sabia', cumprimentos ou CTA genérico.
Divida a MESMA narração em 7 a 11 cenas. O texto concatenado das cenas deve formar a narração.
Cada cena precisa de consulta visual concreta em PT e inglês, overlay de 2-7 palavras e tipo related_image,
related_video ou satisfying. Tecnologia/história priorizam mídia relacionada; satisfying serve para curiosidade/relato.
Retorne somente JSON:
{{"hook":"...","narration":"...","title":"... #shorts","description":"...","tags":["..."],
"scenes":[{{"text":"...","query_pt":"...","query_en":"...","visual_type":"related_image",
"overlay_text":"...","transition":"fade","emphasis":false}}]}}
"""
    error = None
    for _ in range(3):
        response = requests.post(
            f"{settings.groq_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"},
            json={"model": settings.groq_model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.55, "response_format": {"type": "json_object"}}, timeout=120,
        )
        response.raise_for_status()
        data = _extract_json(response.json()["choices"][0]["message"]["content"])
        narration, raw_scenes = str(data.get("narration", "")).strip(), data.get("scenes", [])
        count = len(narration.split())
        try:
            if not minimum_words <= count <= maximum_words + 8 or not 6 <= len(raw_scenes) <= 12:
                raise ValueError(f"invalid storyboard size: {count} words, {len(raw_scenes)} scenes")
            scenes = []
            for item in raw_scenes:
                visual_type = str(item.get("visual_type", "related_image"))
                if visual_type not in VISUAL_TYPES:
                    visual_type = "related_image"
                scenes.append(StoryboardScene(
                    str(item["text"]).strip(), str(item.get("query_pt", topic.title)).strip(),
                    str(item.get("query_en", item.get("query_pt", topic.title))).strip(), visual_type,
                    " ".join(str(item.get("overlay_text", "")).split()[:7]),
                    str(item.get("transition", "fade")), bool(item.get("emphasis", False)),
                ))
            description = str(data.get("description", "")).strip()
            if topic.source_url not in description:
                description += f"\n\nFonte factual: {topic.source_url}"
            plan = ShortPlan(0, float(target), narration, str(data["title"])[:100], description,
                             [str(item) for item in data.get("tags", [])][:12])
            return Storyboard(plan, str(data.get("hook", scenes[0].text)), scenes)
        except (KeyError, ValueError) as exc:
            error = exc
            prompt += f"\nCorrija a tentativa anterior: {exc}."
    raise error or RuntimeError("Groq failed to create storyboard")


def align_storyboard(board: Storyboard, audio_duration: float) -> Storyboard:
    counts = [max(1, len(scene.text.split())) for scene in board.scenes]
    total, cursor, aligned = sum(counts), 0.0, []
    for index, (scene, count) in enumerate(zip(board.scenes, counts)):
        end = audio_duration if index == len(counts) - 1 else cursor + audio_duration * count / total
        aligned.append(replace(scene, start=cursor, end=end))
        cursor = end
    return Storyboard(replace(board.plan, end=audio_duration), board.hook, aligned)


def create_original_plan(topic: ContentTopic, settings: ShortsSettings) -> ShortPlan:
    return create_storyboard(topic, settings).plan
