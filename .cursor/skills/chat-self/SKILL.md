---
name: chat-self
description: >-
  聊一聊模式：只用个人目录回答感情、投资、工作经历与教训。
  用户说「聊一聊」「个人模式」「用我的第二自我」时使用。
  写代码、改仓库、查 bug 时不要使用。
---

# 聊一聊

私人目录默认是 `~/.second-self`，可用环境变量 `SELF_ROOT` 覆盖。公开仓库里没有这些内容。

## 每次先做

1. 用当前问题当 query，运行：

```bash
cd /Users/cai.sl/project/second-self
export PYTHONPATH=src
/opt/homebrew/bin/python3.11 -m selfos recall --query "<用户原话>"
```

需要限定线时加 `--line bond|capital|craft|identity`。

2. 回答时分栏：
   - `mine`：已经生效的教训
   - `lived`：经历，还不是教训
   - `borrowed`：别人或 Gemini 的话，未收编前不能当行动依据

3. 没有匹配就直说材料不够。不要编教训。

## 写入

- 新经历：`selfos ingest`
- 别人的话：`selfos note`
- 亲历收成教训：`selfos learn`（要用户确认）
- 收编别人的话：`selfos adopt`（要用户确认）

不要把原始导出或整段聊天原样贴进公开仓库。写完后如需备份，只提交私人仓库 `~/.second-self`。

## 结束

用户说「回到工作」或转去做工程任务：停止读取私人目录，回到工作模式。
