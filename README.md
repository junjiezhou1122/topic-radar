# Topic Radar

把"AI 圈在发生什么"变成飞书文档里的每日选题日报。**agent-driven**：每个 skill 由 Multica autopilot 调度，agent 按 SKILL.md 自己跑。

## Pipeline

```
[ 6 个信号源 ]                  [ 信息流表 ]                 [ 飞书文档日报 ]
                                 飞书 Base
 Show HN  ─┐                                              daily-report-solutions
 PH       ─┤   radar-pull  →  tblErG6cjYrIcZkv  →         daily-report-attention
 X List   ─┤   (agent 自己跑)   (所有信号)                  daily-report-aggregate
 X 关键词 ─┤
 XHS 关键词┤
  ↓ 聚合
AI 注意力聚合 ┘
```

## Skills

| Skill | 频率 | 干什么 |
|---|---|---|
| `radar-pull` | 09:30 daily | agent 自己 curl + treg + ego-browser，写飞书 |
| `daily-report-solutions` | 10:00 daily | Show HN + PH → markdown 日报 |
| `daily-report-attention` | 10:10 daily | X List + X 关键词 + 小红书 → markdown 日报 |
| `daily-report-aggregate` | 10:20 daily | 聚合话题 → markdown 盘点日报 |

## 每个 Skill 的结构

```
skills/<skill-name>/
├── SKILL.md              ← 主入口（agent 必读）
├── prompts/              ← LLM prompt 模板（仅 daily-report-* 需要）
│   └── *.md
├── references/           ← curl/treg/ego-browser 模板（仅 radar-pull 需要）
└── state/                ← 运行时状态（gitignore）
```

`radar-pull` 没有固定 .py 入口 —— agent 自己读 references 里的模板，按需调整后执行。

## 飞书资产

- Base: `选题雷达` (`Z5FQbkFg8ayi6CstJ2jcQfzWnJg`)
- 信息流表: `tblErG6cjYrIcZkv`（所有原始信号，dedup by 来源:原始ID）
- 飞书文档库: `选题雷达日报/{方案组, 注意力组, 聚合组}/日报·*·YYYY-MM-DD.md`

## 数据覆盖目标（per group per day）

| 源 | 目标 | 实测 |
|---|---|---|
| Show HN | ≥150 | 7 天窗口 + 分页 |
| Product Hunt | ≥30 | RSS 50 条 |
| X AI 圈 List | ≥100 | ego-browser 滚动到无新文章 |
| X 关键词 | ≥100 | 16 词 × top 10 |
| 小红书 AI 关键词 | ≥50 | 10 词 × top 10 |
| AI 注意力聚合 | ≥10 | topic 级派生 |

## 调度

由 **Multica autopilot**：
```bash
multica autopilot create --agent <agent> --title "radar-pull" --mode run_only
multica autopilot trigger-add <id> --cron "30 9 * * *" --timezone "Asia/Shanghai"
```

## 迁移历史

- 旧代码 `~/radar/` → `~/radar.archive/`（已归档）
- 旧 launchd `com.radar.{daily,xlist}` 已停用
- v1 → v2 重构：删了固定 Python 入口（不再固定 .py），删了 `screen-*` + `digest`（合并到 `daily-report-*`），改成 references 模板 + agent 自跑
