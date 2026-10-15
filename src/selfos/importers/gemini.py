from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from selfos.store import Store

PROMPT_PREFIX = "Prompted "
MAX_BODY = 8000

CAPITAL = (
    "股票", "仓位", "清仓", "加仓", "减仓", "止损", "止盈", "板块", "行情",
    "基金", "持仓", "买入", "卖出", "涨停", "跌停", "市值", "估值", "财报",
    "etf", "a股", "港股", "美股", "期权", "杠杆", "回撤", "波动",
)
BOND = (
    "恋爱", "分手", "复合", "吵架", "感情", "婚姻", "对象", "女友", "男友",
    "相亲", "暧昧", "表白", "离婚", "家人", "父母", "情绪",
)
CRAFT = (
    "代码", "仓库", "项目", "工作", "开会", "同事", "老板", "产品", "架构",
    "部署", "bug", "复盘", "接口", "需求", "deadline", "晋升", "简历",
)


@dataclass
class ImportResult:
    prompted: int = 0
    episodes: int = 0
    notes: int = 0
    skipped: int = 0
    already: int = 0

    def to_dict(self) -> dict:
        return {
            "prompted": self.prompted,
            "episodes": self.episodes,
            "notes": self.notes,
            "skipped": self.skipped,
            "already": self.already,
        }


def default_export_path(root: Path) -> Path:
    return root / "private" / "gemini-apps" / "我的活动记录.json"


def import_gemini(store: Store, export_path: Path | None = None) -> ImportResult:
    """把 Prompted 活动收成经历，把回复收成 Gemini 名下的 note。不自动 learn。"""
    path = export_path or default_export_path(store.root)
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Gemini 活动导出应为 JSON 数组")
    seen = _load_seen(store)
    result = ImportResult()
    for row in rows:
        title = str(row.get("title") or "")
        if not title.startswith(PROMPT_PREFIX):
            result.skipped += 1
            continue
        result.prompted += 1
        prompt = title[len(PROMPT_PREFIX) :].strip()
        if not prompt:
            result.skipped += 1
            continue
        when = _day(row.get("time"))
        source = _source_key(row.get("time"), prompt)
        if source in seen:
            result.already += 1
            continue
        conversation = _conversation_id(row)
        reply = _reply_text(row)
        line = guess_line(prompt + "\n" + reply)
        episode_title = _short_title(prompt)
        tags = ["source:gemini", f"import:{source}"]
        if conversation:
            tags.append(f"gemini-app:{conversation}")
        episode = store.add_episode(
            line=line,
            title=episode_title,
            body=prompt[:MAX_BODY],
            occurred_on=when,
            tags=tags,
        )
        result.episodes += 1
        note_id = None
        if reply and reply != prompt:
            note = store.add_note(
                person="Gemini",
                title=f"回复：{episode_title}",
                body=reply[:MAX_BODY],
                added_on=when,
            )
            note_id = note.id
            result.notes += 1
        _append_seen(
            store,
            {
                "source": source,
                "time": row.get("time"),
                "line": line,
                "episode": episode.id,
                "note": note_id,
                "conversation": conversation,
            },
        )
        seen.add(source)
    return result


def guess_line(text: str) -> str:
    low = text.casefold()
    scores = {
        "capital": sum(1 for word in CAPITAL if word in low),
        "bond": sum(1 for word in BOND if word in low),
        "craft": sum(1 for word in CRAFT if word in low),
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "identity"
    return best


def _reply_text(row: dict) -> str:
    parts = row.get("safeHtmlItem") or []
    if not parts:
        return ""
    html_text = parts[0].get("html") if isinstance(parts[0], dict) else ""
    return _strip_html(str(html_text or ""))


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text))).strip()


def _conversation_id(row: dict) -> str | None:
    for detail in row.get("details") or []:
        if not isinstance(detail, dict):
            continue
        name = str(detail.get("name") or "")
        match = re.search(r"gemini\.google\.com/app/([0-9a-f]+)", name)
        if match:
            return match.group(1)
    return None


def _day(raw) -> str:
    if not raw:
        return datetime.utcnow().date().isoformat()
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return str(raw)[:10]


def _short_title(text: str) -> str:
    one = re.sub(r"\s+", " ", text).strip()
    return one[:80] if len(one) > 80 else one


def _source_key(time_value, prompt: str) -> str:
    digest = hashlib.sha1(f"{time_value}\n{prompt}".encode("utf-8")).hexdigest()[:16]
    return f"gemini-{digest}"


def _seen_path(store: Store) -> Path:
    return store.index / "imports-gemini.jsonl"


def _load_seen(store: Store) -> set[str]:
    path = _seen_path(store)
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        row = json.loads(text)
        source = row.get("source")
        if source:
            out.add(source)
    return out


def _append_seen(store: Store, row: dict) -> None:
    store.index.mkdir(parents=True, exist_ok=True)
    with _seen_path(store).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
