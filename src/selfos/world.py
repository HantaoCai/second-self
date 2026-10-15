from __future__ import annotations

import json
from pathlib import Path

from selfos.models import WORLD_KINDS, Episode
from selfos.store import Store, StoreError


class WorldError(ValueError):
    pass


def load_pack(path: Path | str) -> dict:
    pack_path = Path(path)
    if pack_path.is_dir():
        pack_path = pack_path / "beats.json"
    data = json.loads(pack_path.read_text(encoding="utf-8"))
    beats = data.get("beats")
    if not isinstance(beats, list) or not beats:
        raise WorldError("世界包至少要有一拍")
    ids = [beat.get("id") for beat in beats]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise WorldError("每一拍都要有唯一 id")
    known = set(ids)
    for beat in beats:
        kind = beat.get("kind")
        if kind not in WORLD_KINDS:
            raise WorldError(f"{beat.get('id')} 的 kind 只能是 news、market、impact")
        if not str(beat.get("title") or "").strip():
            raise WorldError(f"{beat['id']} 缺少标题")
        causes = beat.get("causes") or []
        if not isinstance(causes, list):
            raise WorldError(f"{beat['id']} 的 causes 必须是列表")
        missing = [cause for cause in causes if cause not in known]
        if missing:
            raise WorldError(f"{beat['id']} 引用了包外的原因: {', '.join(missing)}")
    order_beats(beats)
    return data


def order_beats(beats: list[dict]) -> list[dict]:
    by_id = {beat["id"]: beat for beat in beats}
    inbound = {beat["id"]: 0 for beat in beats}
    children: dict[str, list[str]] = {beat["id"]: [] for beat in beats}
    order_index = {beat["id"]: index for index, beat in enumerate(beats)}
    for beat in beats:
        for cause in beat.get("causes") or []:
            children[cause].append(beat["id"])
            inbound[beat["id"]] += 1
    ready = sorted((beat_id for beat_id, degree in inbound.items() if degree == 0), key=order_index.get)
    ordered: list[dict] = []
    while ready:
        beat_id = ready.pop(0)
        ordered.append(by_id[beat_id])
        for nxt in children[beat_id]:
            inbound[nxt] -= 1
            if inbound[nxt] == 0:
                ready.append(nxt)
        ready.sort(key=order_index.get)
    if len(ordered) != len(beats):
        raise WorldError("因果成环")
    return ordered


def chain_text(beats: list[dict]) -> str:
    lines = []
    for beat in order_beats(beats):
        hits = "、".join(beat.get("hits") or []) or "未点名"
        body = str(beat.get("body") or "").strip()
        lines.append(f"[{beat['kind']}] {beat['title']}。打到：{hits}。{body}".rstrip())
    return "\n".join(lines)


def record_reaction(
    store: Store,
    *,
    beat_id: str,
    line: str,
    title: str,
    body: str,
    occurred_on: str | None = None,
) -> Episode:
    """世界里发生的事不是我的经历。我看到之后做了什么，才写回来。"""
    if not beat_id.strip():
        raise StoreError("要写明这是对世界里哪一拍的反应")
    return store.add_episode(
        line=line,
        title=title,
        body=body,
        occurred_on=occurred_on,
        tags=[f"world:{beat_id}"],
        world_beat=beat_id,
    )
