import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shorts.editor import write_srt
from shorts.auto_content import align_storyboard
from shorts.media import attribution_text
from shorts.models import MediaAsset, ShortPlan, Storyboard, StoryboardScene, TranscriptSegment
from shorts.settings import load_settings
from shorts.editor import create_topic_card


class ShortsPipelineTests(unittest.TestCase):
    def test_plan_duration(self):
        plan = ShortPlan(10.0, 43.5, "texto", "titulo", "descricao", [])
        self.assertEqual(plan.duration, 33.5)

    def test_srt_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.srt"
            write_srt([TranscriptSegment(1.25, 2.5, "Olá mundo")], str(path))
            self.assertIn("00:00:01,250 --> 00:00:02,500", path.read_text())

    def test_groq_key_from_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text('{"shorts": {"groq_model": "test-model"}}')
            with patch.dict(os.environ, {"GROQ_API_KEY": "secret"}):
                settings = load_settings(str(config))
            self.assertEqual(settings.groq_api_key, "secret")
            self.assertEqual(settings.groq_model, "test-model")

    def test_topic_card(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "card.jpg"
            create_topic_card("Uma curiosidade de teste", "curiosidade", str(path))
            self.assertTrue(path.is_file())

    def test_storyboard_alignment_uses_audio_duration(self):
        plan = ShortPlan(0, 30, "um dois três quatro", "t", "d", [])
        board = Storyboard(plan, "um", [
            StoryboardScene("um dois", "q", "q", "related_image"),
            StoryboardScene("três quatro", "q", "q", "related_image"),
        ])
        aligned = align_storyboard(board, 10.0)
        self.assertEqual(aligned.scenes[0].end, 5.0)
        self.assertEqual(aligned.scenes[-1].end, 10.0)

    def test_attribution_is_deduplicated(self):
        asset = MediaAsset("x", "image", "pexels", "https://example.test/1", "Autor", "Pexels License")
        self.assertEqual(attribution_text([asset, asset]).count("example.test"), 1)

    def test_invalid_privacy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text('{"shorts":{"groq_api_key":"x","youtube_privacy":"friends"}}')
            with self.assertRaises(ValueError):
                load_settings(str(config))


if __name__ == "__main__":
    unittest.main()
