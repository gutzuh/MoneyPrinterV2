import asyncio
from pathlib import Path

import edge_tts


async def _save(text: str, voice: str, output_path: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate="+4%")
    await communicate.save(output_path)


def synthesize(text: str, voice: str, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(_save(text, voice, output_path))
    return output_path
