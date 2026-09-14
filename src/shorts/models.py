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
