from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from selfos.adapters.jev import JevDecision
from selfos.decide import decide, default_playbook_dir, load_json
from selfos.importers.gemini import default_export_path, import_gemini
from selfos.recall import recall
from selfos.store import Store, default_root
from selfos.world import chain_text, load_pack, record_reaction


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="selfos", description="第二自我")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_cmd = sub.add_parser("init", help="准备一份空的个人目录")
    _add_root(init_cmd)

    ingest = sub.add_parser("ingest", help="记下一段我的经历")
    _add_root(ingest)
    ingest.add_argument("--line", required=True, choices=["bond", "capital", "craft", "identity"])
    ingest.add_argument("--title", required=True)
    ingest.add_argument("--body")
    ingest.add_argument("--file")
    ingest.add_argument("--on")

    note = sub.add_parser("note", help="收下别人的材料，先不变成我的教训")
    _add_root(note)
    note.add_argument("--person", required=True)
    note.add_argument("--title", required=True)
    note.add_argument("--body")
    note.add_argument("--file")
    note.add_argument("--on")

    learn = sub.add_parser("learn", help="从我的一段经历收成教训")
    _add_root(learn)
    learn.add_argument("--episode", required=True)
    learn.add_argument("--claim", required=True)
    learn.add_argument("--because", required=True)
    learn.add_argument("--supersedes")

    adopt = sub.add_parser("adopt", help="把别人的某条材料收编成我的教训")
    _add_root(adopt)
    adopt.add_argument("--person", required=True)
    adopt.add_argument("--note", required=True)
    adopt.add_argument("--line", required=True, choices=["bond", "capital", "craft", "identity"])
    adopt.add_argument("--claim", required=True)
    adopt.add_argument("--because", required=True)
    adopt.add_argument("--supersedes")

    recall_cmd = sub.add_parser("recall", help="分开召回教训、经历和别人的话")
    _add_root(recall_cmd)
    recall_cmd.add_argument("--query", required=True)
    recall_cmd.add_argument("--line")

    import_cmd = sub.add_parser("import-gemini", help="把 Gemini 活动导出收进经历与 note，不自动收成教训")
    _add_root(import_cmd)
    import_cmd.add_argument("--file", help="活动记录 JSON，默认读私人目录里的导出")

    decide_cmd = sub.add_parser("decide", help="在允许的动作里做一次选择")
    _add_root(decide_cmd)
    decide_cmd.add_argument("--playbook", required=True)
    decide_cmd.add_argument("--situation", required=True)
    decide_cmd.add_argument("--skills", default="playbooks/skills.json")

    react = sub.add_parser("react", help="把我对世界里某一拍的反应写回经历")
    _add_root(react)
    react.add_argument("--beat", required=True)
    react.add_argument("--line", required=True, choices=["bond", "capital", "craft", "identity"])
    react.add_argument("--title", required=True)
    react.add_argument("--body", required=True)

    world = sub.add_parser("world", help="检查或播放一个你写的世界")
    world_sub = world.add_subparsers(dest="world_cmd", required=True)
    check = world_sub.add_parser("check")
    check.add_argument("--pack", required=True)
    play = world_sub.add_parser("play")
    play.add_argument("--pack", required=True)

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    if args.cmd == "world":
        pack = load_pack(_pack_path(args.pack))
        ordered = chain_text(pack["beats"])
        if args.world_cmd == "check":
            print(f"ok {pack.get('title', args.pack)}")
        print(ordered)
        return 0

    store = Store(_root(args))
    if args.cmd == "init":
        store.init()
        print(store.root)
        return 0
    if args.cmd == "ingest":
        episode = store.add_episode(
            line=args.line,
            title=args.title,
            body=_body(args.body, args.file),
            occurred_on=args.on,
        )
        print(episode.id)
        return 0
    if args.cmd == "note":
        note = store.add_note(
            person=args.person,
            title=args.title,
            body=_body(args.body, args.file),
            added_on=args.on,
        )
        print(note.id)
        return 0
    if args.cmd == "learn":
        lesson = store.learn(episode_id=args.episode, claim=args.claim, because=args.because, supersedes=args.supersedes)
        print(lesson.id)
        return 0
    if args.cmd == "adopt":
        lesson = store.adopt(
            person=args.person,
            note_id=args.note,
            line=args.line,
            claim=args.claim,
            because=args.because,
            supersedes=args.supersedes,
        )
        print(lesson.id)
        return 0
    if args.cmd == "recall":
        found = recall(store, args.query, line=args.line)
        payload = {
            "mine": [row.to_dict() for row in found.mine],
            "lived": [row.to_dict() for row in found.lived],
            "borrowed": [row.to_dict() for row in found.borrowed],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "import-gemini":
        store.init()
        path = Path(args.file).expanduser() if args.file else default_export_path(store.root)
        result = import_gemini(store, path)
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "decide":
        playbook = load_json(_playbook_path(args.playbook))
        skills = load_json(args.skills)
        result = decide(store, playbook, args.situation, skills, JevDecision())
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "react":
        episode = record_reaction(
            store,
            beat_id=args.beat,
            line=args.line,
            title=args.title,
            body=args.body,
        )
        print(episode.id)
        return 0
    raise AssertionError(args.cmd)


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", default=None, help="个人内容目录，默认 ~/.second-self")


def _root(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root).expanduser()
    return default_root()


def _body(text: str | None, file_path: str | None) -> str:
    if file_path:
        return Path(file_path).read_text(encoding="utf-8")
    if text:
        return text
    raise ValueError("要给 --body 或 --file")


def _playbook_path(name: str) -> Path:
    path = Path(name)
    if path.exists():
        return path
    return default_playbook_dir() / f"{name}.json"


def _pack_path(name: str) -> Path:
    path = Path(name)
    if path.exists():
        return path
    return Path("worlds") / name


if __name__ == "__main__":
    raise SystemExit(main())
