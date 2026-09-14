from faster_whisper import WhisperModel

from .models import TranscriptSegment, WordTiming
from .settings import ShortsSettings


def transcribe(
    media_path: str,
    settings: ShortsSettings,
    words_per_caption: int | None = None,
) -> list[TranscriptSegment]:
    model = WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    segments, _ = model.transcribe(
        media_path,
        vad_filter=True,
        language=None,
        word_timestamps=words_per_caption is not None,
    )
    resolved = list(segments)
    if words_per_caption is None:
        return [
            TranscriptSegment(float(segment.start), float(segment.end), segment.text.strip())
            for segment in resolved
            if segment.text.strip()
        ]

    captions: list[TranscriptSegment] = []
    for segment in resolved:
        words = [word for word in (segment.words or []) if word.word.strip()]
        for index in range(0, len(words), words_per_caption):
            group = words[index:index + words_per_caption]
            captions.append(
                TranscriptSegment(
                    float(group[0].start),
                    float(group[-1].end),
                    " ".join(word.word.strip() for word in group),
                )
            )
    return captions


def transcribe_words(media_path: str, settings: ShortsSettings) -> list[WordTiming]:
    model = WhisperModel(settings.whisper_model, device=settings.whisper_device, compute_type=settings.whisper_compute_type)
    segments, _ = model.transcribe(media_path, vad_filter=True, language="pt", word_timestamps=True)
    return [WordTiming(word.word.strip(), float(word.start), float(word.end))
            for segment in segments for word in (segment.words or []) if word.word.strip()]
