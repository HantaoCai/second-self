from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from enum import Enum
from uuid import uuid4


class Line(str, Enum):
    bond = "bond"  # 感情
    capital = "capital"  # 投资
    craft = "craft"  # 工作
    identity = "identity"  # 跨线的慢变量


class Origin(str, Enum):
    lived = "lived"  # 我亲历，再收成教训
    adopted = "adopted"  # 从别人的材料里明确收编
    quoted = "quoted"  # 还停在别人名下


LINES = {item.value for item in Line}
LESSON_ORIGINS = {Origin.lived.value, Origin.adopted.value}
WORLD_KINDS = {"news", "market", "impact"}


def new_id(prefix: str, on: str | None = None) -> str:
    day = on or date.today().isoformat()
    compact = day.replace("-", "")
    return f"{prefix}-{compact}-{uuid4().hex[:8]}"


@dataclass
class Episode:
    id: str
    line: str
    title: str
    body: str
    occurred_on: str
    tags: list[str] = field(default_factory=list)
    world_beat: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SourceNote:
    """别人的材料。在被 adopt 之前，它不是我的教训。"""

    id: str
    person: str
    title: str
    body: str
    added_on: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Lesson:
    id: str
    line: str
    claim: str
    because: str
    origin: str
    formed_on: str
    source_episodes: list[str] = field(default_factory=list)
    source_person: str | None = None
    source_note: str | None = None
    supersedes: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
