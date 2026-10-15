# 第二自我

一个人一份、会随材料长大的助手。它记住你怎么走过感情、投资和工作，把这些收成可以取代的教训，再在你允许的动作里帮你选。你以后也可以自己编一个世界，让一条新闻打到市场，再打到某一件事上。

这不是聊天人设。模型、记忆服务、技能都是外挂。你提交进 `corpus/` 的材料才是本体。

## 别人已经做成了什么

公开项目里，相近的一块一块都有，整套没有。

- [PersonaOS](https://github.com/serafim-builds/PersonaOS)、[LifeGraph](https://lifegraph.dev/) 把一个人的生活写成你自己拥有的 Markdown / JSONL，能处理前后矛盾。
- [Letta](https://github.com/letta-ai/letta)、[iai-personal-memory-engine](https://github.com/CodeAbra/iai-personal-memory-engine) 是会长期记住对话的 agent 底座。
- [YuriOS](https://github.com/yuri-os/YuriOS)、[Vera](https://github.com/sinhaankur/cognitive-twin-agent) 是本地陪伴：人格、声音、持续运行。
- Jev / Kev 把「状态」收成带置信度的选择。你在量化看板里已经这样用它做个股定性。
- Haven 这类产品的方向是记住你怎么做决定，但是商业系统，不是你能一点点提交自己三条线的仓库。

缺的是中间这条缝：亲历和学来的必须分开；决策不许自己发明动作；世界是你写的因果，播放它不会自动变成你的人生。

## 四层

```text
corpus/     这个人。经历、别人的材料、教训。一份目录一个人。
playbooks/  允许做什么。高风险动作不进选项。
worlds/     你编的因果。新闻 → 波动 → 打到某件事。
adapters/   Jev、以后的记忆系统。换掉不影响本体。
```

三条线是 `bond`（感情）、`capital`（投资）、`craft`（工作）。`identity` 只放跨三条线都成立的慢变量。

以后若开放给别人养自己的助手：每人复制一份空的 corpus，世界包可以共用。不要把谁的 corpus 并进别人的经历。

## 你怎么往里添材料

```bash
python3 -m selfos init

python3 -m selfos ingest --line capital --title "割在地板" \
  --body "恐慌那天清仓，第二天涨回来"

python3 -m selfos learn --episode <上一步打印的 id> \
  --claim "先写出为什么跌，再决定动不动" \
  --because "第二天证明当时没有新事实"

python3 -m selfos note --person 某人 --title "别急" \
  --body "下跌时先看是不是情绪"

python3 -m selfos adopt --person 某人 --note <note id> --line capital \
  --claim "下跌先分辨情绪和基本面" \
  --because "我认可这句话，并决定以后照做"
```

`--file` 可以代替 `--body`。私密原文放 `corpus/private/`，这个目录不入库。

召回和决策：

```bash
python3 -m selfos recall --line capital --query "下跌 情绪"
python3 -m selfos decide --playbook capital_review --situation "相关板块今天跌了"
```

没配 `TYPESAFE_API_KEY` 时，`decide` 只交出简报：用上了哪些教训、选项有哪些。它不会编一个选择。配了 key 且安装 `typesafe-sdk` 后，才走 Jev。本地的 Kev 只要兼容 TypeSafe System One，改 `TYPESAFE_BASE_URL` 即可。置信度低于剧本里的门槛，结果是 `needs_human`。

旧教训被新教训取代后，召回只给还生效的那条。不能用感情线上的教训取代投资线上的。

## 自己编一个世界

`worlds/sample-shock/` 是一条示例链：监管新闻，板块下跌，打到「还拿不拿这个主题」。

```bash
python3 -m selfos world play --pack sample-shock
python3 -m selfos react --beat hit-hold --line capital \
  --title "我没动" --body "对照旧教训，这次选择不动"
```

新的世界是一个目录加一份 `beats.json`。每一拍有 `id`、`kind`（`news` / `market` / `impact`）、`title`、`causes`、`hits`。因果不能成环，也不能引用包里没有的原因。

世界播放不会写进 corpus。你对那一拍的反应用 `react` 写下之后，才是你的经历；再要用 `learn` 才会变成教训。

## 测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
