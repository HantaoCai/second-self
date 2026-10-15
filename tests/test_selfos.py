from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from selfos.__main__ import main
from selfos.decide import UnavailableDecision, choice_criteria, decide, load_json
from selfos.recall import recall
from selfos.store import Store, StoreError
from selfos.world import chain_text, load_pack, record_reaction


ROOT = Path(__file__).resolve().parents[1]


class FakeDecision:
    def __init__(self, answer: dict | None) -> None:
        self.answer = answer

    def choose(self, *, state, instructions, criteria):
        return self.answer


class Invariants(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "corpus")
        self.store.init()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_quoted_note_is_not_a_lesson(self) -> None:
        note = self.store.add_note(person="某人", title="别急", body="下跌时先看是不是情绪")
        found = recall(self.store, "下跌 情绪")
        self.assertEqual(found.mine, [])
        self.assertEqual(found.borrowed[0].id, note.id)

    def test_adopt_requires_real_note(self) -> None:
        with self.assertRaises(StoreError):
            self.store.adopt(
                person="某人",
                note_id="nt-missing",
                line="capital",
                claim="先看情绪",
                because="他说过",
            )

    def test_adopt_keeps_provenance(self) -> None:
        note = self.store.add_note(person="某人", title="别急", body="下跌时先看是不是情绪")
        lesson = self.store.adopt(
            person="某人",
            note_id=note.id,
            line="capital",
            claim="下跌先分辨情绪和基本面",
            because="我认可他这句话，并决定以后照做",
        )
        self.assertEqual(lesson.origin, "adopted")
        self.assertEqual(lesson.source_person, "某人")
        found = recall(self.store, "下跌 基本面")
        self.assertEqual(found.mine[0].id, lesson.id)
        self.assertEqual(found.borrowed[0].id, note.id)

    def test_supersede_retires_old_lesson(self) -> None:
        episode = self.store.add_episode(line="capital", title="割在地板", body="恐慌那天清仓，第二天涨回来")
        old = self.store.learn(
            episode_id=episode.id,
            claim="一跌就清",
            because="那次我吓到了",
        )
        new = self.store.learn(
            episode_id=episode.id,
            claim="先写出为什么跌，再决定动不动",
            because="清仓的第二天证明当时没有新事实",
            supersedes=old.id,
        )
        active = self.store.active_lessons("capital")
        self.assertEqual([row.id for row in active], [new.id])

    def test_cannot_cross_lines_when_superseding(self) -> None:
        episode = self.store.add_episode(line="craft", title="一次返工", body="没写清边界就开工")
        old = self.store.learn(episode_id=episode.id, claim="先写边界", because="那次返工")
        other = self.store.add_episode(line="bond", title="一次争吵", body="当场下了结论")
        with self.assertRaises(StoreError):
            self.store.learn(episode_id=other.id, claim="先停", because="想取代工作教训", supersedes=old.id)

    def test_act_skill_never_enters_choices(self) -> None:
        playbook = load_json(ROOT / "playbooks" / "capital_review.json")
        skills = load_json(ROOT / "playbooks" / "skills.json")
        criteria = choice_criteria(playbook, skills)
        self.assertNotIn("place_order", criteria)
        self.assertIn("write_review", criteria)
        self.assertIn("先不动作", criteria)

    def test_missing_model_returns_brief_not_a_choice(self) -> None:
        playbook = load_json(ROOT / "playbooks" / "after_shock.json")
        skills = load_json(ROOT / "playbooks" / "skills.json")
        result = decide(self.store, playbook, "示例行业下跌", skills, UnavailableDecision())
        self.assertEqual(result.status, "brief")
        self.assertIsNone(result.choice)
        self.assertNotIn("place_order", result.criteria)

    def test_low_confidence_stays_with_human(self) -> None:
        playbook = load_json(ROOT / "playbooks" / "capital_review.json")
        skills = load_json(ROOT / "playbooks" / "skills.json")
        result = decide(
            self.store,
            playbook,
            "继续拿着",
            skills,
            FakeDecision({"choice": "先不动作", "confidence": 0.2, "probabilities": {}}),
        )
        self.assertEqual(result.status, "needs_human")

    def test_illegal_choice_is_dropped(self) -> None:
        playbook = load_json(ROOT / "playbooks" / "capital_review.json")
        result = decide(
            self.store,
            playbook,
            "买",
            [],
            FakeDecision({"choice": "place_order", "confidence": 0.99}),
        )
        self.assertEqual(result.status, "brief")
        self.assertIsNone(result.choice)

    def test_world_chain_and_reaction_are_separate(self) -> None:
        pack = load_pack(ROOT / "worlds" / "sample-shock")
        text = chain_text(pack["beats"])
        self.assertIn("[news]", text)
        self.assertIn("[market]", text)
        self.assertIn("[impact]", text)
        self.assertEqual(self.store.lessons(), [])
        episode = record_reaction(
            self.store,
            beat_id="hit-hold",
            line="capital",
            title="我没动",
            body="新闻打到示例行业，我对照旧教训选择不动",
        )
        self.assertEqual(episode.world_beat, "hit-hold")
        self.assertEqual(self.store.lessons(), [])

    def test_world_cycle_is_rejected(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump(
                {
                    "beats": [
                        {"id": "a", "kind": "news", "title": "甲", "causes": ["b"]},
                        {"id": "b", "kind": "market", "title": "乙", "causes": ["a"]},
                    ]
                },
                handle,
            )
            path = handle.name
        with self.assertRaises(ValueError):
            load_pack(path)

    def test_cli_init_and_world_play(self) -> None:
        root = Path(self.tmp.name) / "cli-corpus"
        self.assertEqual(main(["init", "--root", str(root)]), 0)
        self.assertTrue((root / "identity" / "principles.md").is_file())
        self.assertEqual(main(["world", "play", "--pack", "sample-shock"]), 0)

    def test_each_store_is_its_own_person(self) -> None:
        other = Store(Path(self.tmp.name) / "someone-else")
        other.init()
        self.store.add_episode(line="bond", title="我的", body="只属于这一份 corpus")
        self.assertEqual(other.episodes(), [])


if __name__ == "__main__":
    unittest.main()
