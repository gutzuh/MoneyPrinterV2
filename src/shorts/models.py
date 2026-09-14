from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class ShortPlan:
    start: float
    end: float
    narration: str
    title: str
    description: str
    tags: list[str]

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class ContentTopic:
    category: str
    title: str
    facts: str
    source_name: str
    source_url: str


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class StoryboardScene:
    text: str
    query_pt: str
    query_en: str
    visual_type: str
    overlay_text: str = ""
    transition: str = "fade"
    emphasis: bool = False
    start: float = 0.0
    end: float = 0.0


@dataclass(frozen=True)
class Storyboard:
    plan: ShortPlan
    hook: str
    scenes: list[StoryboardScene]


@dataclass(frozen=True)
class MediaAsset:
    path: str
    kind: str
    provider: str
    source_url: str
    author: str = ""
    license_name: str = ""
    query: str = ""
