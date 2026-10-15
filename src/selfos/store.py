from __future__ import annotations

import json
from dataclasses import fields
from datetime import date
from pathlib import Path

from selfos.models import (
    LESSON_ORIGINS,
    LINES,
    Episode,
    Lesson,
    SourceNote,
    new_id,
)


class StoreError(ValueError):
    pass


class Store:
    """一份 corpus 就是一个人。追加写，不改旧行。"""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.index = self.root / "index"

    def init(self) -> None:
        for line in ("bond", "capital", "craft"):
            (self.root / "lines" / line).mkdir(parents=True, exist_ok=True)
        (self.root / "people").mkdir(parents=True, exist_ok=True)
        (self.root / "private").mkdir(parents=True, exist_ok=True)
        self.index.mkdir(parents=True, exist_ok=True)
        principles = self.root / "identity" / "principles.md"
        if not principles.exists():
            principles.parent.mkdir(parents=True, exist_ok=True)
            principles.write_text(
                "# 慢变量\n\n"
                "只写跨感情、投资、工作都成立的底线。\n"
                "空着就空着。不要让模型帮你编。\n"
                "真要收成教训，用 `selfos learn` 或 `selfos adopt`，不要只改这个文件。\n",
                encoding="utf-8",
            )

    def add_episode(
        self,
        *,
        line: str,
        title: str,
        body: str,
        occurred_on: str | None = None,
        tags: list[str] | None = None,
        world_beat: str | None = None,
    ) -> Episode:
        self._check_line(line)
        episode = Episode(
            id=new_id("ep", occurred_on),
            line=line,
            title=title.strip(),
            body=body.strip(),
            occurred_on=occurred_on or date.today().isoformat(),
            tags=list(tags or []),
            world_beat=world_beat,
        )
        if not episode.title or not episode.body:
            raise StoreError("经历要有标题和正文")
        self._append("episodes.jsonl", episode.to_dict())
        return episode

    def add_note(self, *, person: str, title: str, body: str, added_on: str | None = None) -> SourceNote:
        person = person.strip()
        if not person:
            raise StoreError("别人的材料要写明是谁")
        note = SourceNote(
            id=new_id("nt", added_on),
            person=person,
            title=title.strip(),
            body=body.strip(),
            added_on=added_on or date.today().isoformat(),
        )
        if not note.title or not note.body:
            raise StoreError("别人的材料要有标题和正文")
        self._append("notes.jsonl", note.to_dict())
        return note

    def learn(
        self,
        *,
        episode_id: str,
        claim: str,
        because: str,
        supersedes: str | None = None,
        formed_on: str | None = None,
    ) -> Lesson:
        episode = self.get_episode(episode_id)
        if episode is None:
            raise StoreError("没有这段经历，不能收成我的教训")
        return self._write_lesson(
            line=episode.line,
            claim=claim,
            because=because,
            origin="lived",
            formed_on=formed_on,
            source_episodes=[episode.id],
            supersedes=supersedes,
        )

    def adopt(
        self,
        *,
        person: str,
        note_id: str,
        line: str,
        claim: str,
        because: str,
        supersedes: str | None = None,
        formed_on: str | None = None,
    ) -> Lesson:
        note = self.get_note(note_id)
        if note is None:
            raise StoreError("没有这条别人的材料，不能收编")
        if note.person != person:
            raise StoreError("材料和人不匹配")
        return self._write_lesson(
            line=line,
            claim=claim,
            because=because,
            origin="adopted",
            formed_on=formed_on,
            source_person=note.person,
            source_note=note.id,
            supersedes=supersedes,
        )

    def episodes(self) -> list[Episode]:
        return [Episode(**_pick(Episode, row)) for row in self._read("episodes.jsonl")]

    def notes(self, person: str | None = None) -> list[SourceNote]:
        rows = [SourceNote(**_pick(SourceNote, row)) for row in self._read("notes.jsonl")]
        if person is None:
            return rows
        return [row for row in rows if row.person == person]

    def lessons(self) -> list[Lesson]:
        return [Lesson(**_pick(Lesson, row)) for row in self._read("lessons.jsonl")]

    def get_episode(self, episode_id: str) -> Episode | None:
        return next((row for row in self.episodes() if row.id == episode_id), None)

    def get_note(self, note_id: str) -> SourceNote | None:
        return next((row for row in self.notes() if row.id == note_id), None)

    def get_lesson(self, lesson_id: str) -> Lesson | None:
        return next((row for row in self.lessons() if row.id == lesson_id), None)

    def active_lessons(self, line: str | None = None) -> list[Lesson]:
        rows = self.lessons()
        retired = {row.supersedes for row in rows if row.supersedes}
        active = [row for row in rows if row.id not in retired]
        if line is None:
            return active
        self._check_line(line)
        return [row for row in active if row.line == line]

    def _write_lesson(
        self,
        *,
        line: str,
        claim: str,
        because: str,
        origin: str,
        formed_on: str | None,
        source_episodes: list[str] | None = None,
        source_person: str | None = None,
        source_note: str | None = None,
        supersedes: str | None = None,
    ) -> Lesson:
        self._check_line(line)
        if origin not in LESSON_ORIGINS:
            raise StoreError("教训只能来自亲历或明确收编")
        if supersedes:
            old = self.get_lesson(supersedes)
            if old is None:
                raise StoreError("要取代的教训不存在")
            if old.line != line:
                raise StoreError("不能跨线取代")
            if supersedes in {row.supersedes for row in self.lessons()}:
                raise StoreError("这条教训已经被取代")
        lesson = Lesson(
            id=new_id("ls", formed_on),
            line=line,
            claim=claim.strip(),
            because=because.strip(),
            origin=origin,
            formed_on=formed_on or date.today().isoformat(),
            source_episodes=list(source_episodes or []),
            source_person=source_person,
            source_note=source_note,
            supersedes=supersedes,
        )
        if not lesson.claim or not lesson.because:
            raise StoreError("教训要写明主张，以及因为什么")
        self._append("lessons.jsonl", lesson.to_dict())
        return lesson

    def _check_line(self, line: str) -> None:
        if line not in LINES:
            raise StoreError(f"未知的线: {line}")

    def _append(self, name: str, row: dict) -> None:
        self.index.mkdir(parents=True, exist_ok=True)
        path = self.index / name
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _read(self, name: str) -> list[dict]:
        path = self.index / name
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text:
                rows.append(json.loads(text))
        return rows


def _pick(cls, row: dict) -> dict:
    names = {item.name for item in fields(cls)}
    return {key: value for key, value in row.items() if key in names}
