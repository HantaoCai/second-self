from __future__ import annotations

import os


class JevDecision:
    """TypeSafe / Jev / 兼容的本地模型。只做选择，不执行动作。"""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or os.getenv("TYPESAFE_MODEL") or None

    def choose(self, *, state: dict, instructions: str, criteria: dict[str, str]) -> dict | None:
        if not (os.getenv("TYPESAFE_API_KEY") or "").strip():
            return None
        try:
            from typesafe_sdk import Choice, TypeSafeClient
        except ImportError:
            return {"error": "未安装 typesafe-sdk"}
        try:
            client = TypeSafeClient()
            response = client.system_one(
                state=state,
                questions={
                    "next": Choice(instructions=instructions, criteria=criteria),
                },
                model=self.model,
            )
            answer = response.answers["next"]
            probabilities = {
                key: round(float(value), 4) for key, value in (answer.probabilities or {}).items()
            }
            confidence = None if answer.confidence is None else round(float(answer.confidence), 4)
            return {
                "choice": answer.choice,
                "confidence": confidence,
                "probabilities": probabilities,
            }
        except Exception as exc:  # noqa: BLE001 — 模型失败不能变成一个假决定
            return {"error": f"{type(exc).__name__}: {exc}"}
