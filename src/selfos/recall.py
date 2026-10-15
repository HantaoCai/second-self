from __future__ import annotations

from dataclasses import dataclass

from selfos.models import Episode, Lesson, SourceNote
from selfos.store import Store


@dataclass
class Recall:
    mine: list[Lesson]
    lived: list[Episode]
    borrowed: list[SourceNote]


def recall(store: Store, query: str, *, line: str | None = None, limit: int = 5) -> Recall:
    """我的有效教训、我的经历、还没收编的别人的话，分三栏返回。"""
    mine = _rank_lessons(store, query, line=line, limit=limit)
    lived = _rank_episodes(store.episodes(), query, line=line, limit=limit)
    borrowed = _rank_notes(store.notes(), query, limit=limit)
    return Recall(mine=mine, lived=lived, borrowed=borrowed)


def _rank_lessons(store: Store, query: str, *, line: str | None, limit: int) -> list[Lesson]:
    rows = list(store.active_lessons(line))
    if line and line != "identity":
        seen = {row.id for row in rows}
        for item in store.active_lessons("identity"):
            if item.id not in seen:
                rows.append(item)
    return _top(rows, query, limit, lambda row: f"{row.claim}\n{row.because}")


def _rank_episodes(episodes: list[Episode], query: str, *, line: str | None, limit: int) -> list[Episode]:
    rows = episodes if line is None else [row for row in episodes if row.line == line or row.line == "identity"]
    return _top(rows, query, limit, lambda row: f"{row.title}\n{row.body}\n{' '.join(row.tags)}")


def _rank_notes(notes: list[SourceNote], query: str, limit: int) -> list[SourceNote]:
    return _top(notes, query, limit, lambda row: f"{row.person}\n{row.title}\n{row.body}")


def _top(rows, query: str, limit: int, text_of):
    scored = [(_score(text_of(row), query), index, row) for index, row in enumerate(rows)]
    if query.strip():
        scored = [item for item in scored if item[0] > 0]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [row for _, _, row in scored[:limit]]


def _score(text: str, query: str) -> int:
    tokens = [part for part in query.casefold().split() if part]
    if not tokens:
        return 0
    haystack = text.casefold()
    return sum(1 for token in tokens if token in haystack)
