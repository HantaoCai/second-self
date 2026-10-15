from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from selfos.recall import recall
from selfos.store import Store


class DecisionPort(Protocol):
    def choose(self, *, state: dict, instructions: str, criteria: dict[str, str]) -> dict | None:
        """返回 choice / confidence / probabilities。没有模型时返回 None。"""


class UnavailableDecision:
    def choose(self, *, state: dict, instructions: str, criteria: dict[str, str]) -> dict | None:
        return None


@dataclass
class Decision:
    status: str
    criteria: dict[str, str]
    state: dict
    choice: str | None = None
    confidence: float | None = None
    probabilities: dict | None = None
    detail: str | None = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "choice": self.choice,
            "confidence": self.confidence,
            "probabilities": self.probabilities,
            "detail": self.detail,
            "criteria": self.criteria,
            "state": self.state,
        }


def choice_criteria(playbook: dict, skills: list[dict]) -> dict[str, str]:
    """选项来自剧本。技能只有低风险且明确暴露的才能加进来。下单这类动作永远不进选项。"""
    criteria = {str(key): str(value) for key, value in playbook["criteria"].items()}
    line = playbook["line"]
    for skill in skills:
        if skill.get("risk") == "act":
            continue
        if not skill.get("expose"):
            continue
        if skill.get("risk") not in {"read", "draft"}:
            continue
        lines = skill.get("lines") or []
        if "*" not in lines and line not in lines:
            continue
        criteria[str(skill["id"])] = str(skill["description"])
    return criteria


def load_json(path: Path | str) -> dict | list:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def decide(
    store: Store,
    playbook: dict,
    situation: str,
    skills: list[dict],
    port: DecisionPort,
) -> Decision:
    criteria = choice_criteria(playbook, skills)
    found = recall(store, situation, line=playbook["line"])
    state = {
        "situation": situation,
        "line": playbook["line"],
        "my_lessons": [
            {
                "id": row.id,
                "origin": row.origin,
                "claim": row.claim,
                "because": row.because,
            }
            for row in found.mine
        ],
        "borrowed": [
            {"person": row.person, "title": row.title, "body": row.body}
            for row in found.borrowed
        ],
        "rule": "别人的话单独不能构成行动理由。高风险动作不在选项里。",
    }
    answer = port.choose(
        state=state,
        instructions=str(playbook["instructions"]),
        criteria=criteria,
    )
    if not answer:
        return Decision(status="brief", criteria=criteria, state=state, detail="没有决策模型，只交出材料。")
    if answer.get("error"):
        return Decision(
            status="brief",
            criteria=criteria,
            state=state,
            detail=str(answer["error"]),
        )
    choice = answer.get("choice")
    confidence = answer.get("confidence")
    probabilities = answer.get("probabilities")
    if choice not in criteria:
        return Decision(
            status="brief",
            criteria=criteria,
            state=state,
            detail="模型给了选项之外的答案，已丢弃。",
        )
    threshold = float(playbook.get("min_confidence", 0.6))
    if confidence is None or float(confidence) < threshold:
        return Decision(
            status="needs_human",
            criteria=criteria,
            state=state,
            choice=str(choice),
            confidence=None if confidence is None else float(confidence),
            probabilities=probabilities,
            detail="置信度不够，人来定。",
        )
    return Decision(
        status="chosen",
        criteria=criteria,
        state=state,
        choice=str(choice),
        confidence=float(confidence),
        probabilities=probabilities,
    )


def default_playbook_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "playbooks"
