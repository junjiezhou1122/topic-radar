# TO_HERMES — Topic Radar 配置说明（小马接活专用）

> 周君杰 → 小马（团队 Hermes）· 2026-09-19
> 背景：创哥提议把「选题雷达日报」流水线从周君杰个人 Mac 迁到团队 Hermes 上，由小马用自带 cron 调度。
> 本文是安装 + 配置 + 运行说明，读完照做即可。

## 1. 任务是什么

每天给创哥产出一份「AI 圈在发生什么」的选题情报，落点在飞书 Base「选题雷达」：

```
6 个信号源 ──► 信息流表(tblErG6cjYrIcZkv) ──► 每日 markdown 日报(Base 内 docx block)
Show HN       radar-pull 09:30               daily-report-solutions 10:00 → 方案组日报
Product Hunt                                 daily-report-attention 10:10 → 注意力组日报
X AI 圈 List                                   benchmark-pull 10:30 → 对标账号帖子+评论
X AI 关键词
小红书 AI 关键词
AI 注意力聚合(派生)
```

## 2. 环境要求（你机器上要有）

| 项 | 用途 | 说明 |
|---|---|---|
| `python3` | 跑 scripts/*.py | |
| `curl` | Show HN / Product Hunt | |
| `jq` | references 脚本解析 | |
| `lark-cli` | 读写飞书 Base / 发消息 | **需要 user identity ready**（`lark-cli auth status` 看 user.available） |
| `TIKHUB_API_KEY` | X/小红书/B站/YT/微信 数据源 | **已放在 `skills/radar-pull/.env`，脚本自动读**；也建议 export 到环境变量 |

不需要装：treg、ego-browser（除非你要接 X 源，见第 4 节）。

## 3. 四个 cron（Asia/Shanghai）

| 时间 | 任务 | 入口 |
|---|---|---|
| `30 9 * * *` | radar-pull | 读 `skills/radar-pull/SKILL.md`，按其执行：6 源 → 去重 → 写信息流表 → IM 汇报 |
| `0 10 * * *` | daily-report-solutions | `cd skills/daily-report-solutions && python3 scripts/run.py --group solutions --date <today>`，agent 自己按 prompts/solution.md 当 LLM 产出 |
| `10 10 * * *` | daily-report-attention | 同上，`--group attention` |
| `30 10 * * *` | benchmark-pull | `python3 scripts/benchmark_pull.py`（智能 24h 窗口，漏跑自动回溯 ≤14 天）|

幂等保证：同一天重复跑不会产生重复记录/重复文档（dedup key + find-or-create block），放心重试。

## 4. X 源现状（重点，需要你决策/反馈）

2026-09-19 实测：**tikhub 所有 twitter/web 端点全部返回 400**（`fetch_user_post_tweet` / `fetch_search_timeline` / `fetch_list_timeline` 均失败，失败不计费）。
小红书/B站/YouTube/微信走的 tikhub 端点全部正常。这是 tikhub 上游对 X 的抓取故障，不是我们的 key 问题。

所以 X 三源（List / 关键词）暂时没有可靠数据通道。三条路，请你评估后回复：

- **A. 等 tikhub 恢复**：脚本已就位（`tikhub_x_keyword.sh` / `tikhub_x_list.sh`），恢复当天自动可用，零成本。缺点：不知道等多久。
- **B. ego-browser 留在周君杰 Mac**：X 三源在他的 macOS 上跑（登录态在他机器），09:30 跑完直接写飞书信息流表；小马负责其余全部源 + 日报。缺点：周君杰 Mac 关机/休眠就漏 X 信号。
- **C. 你自己有 X 数据通道吗**：比如 agent-reach skill（支持 Twitter/X）、或团队有 X API key？如果有，最干净，全归你。

## 5. 飞书权限

- Base「选题雷达」`Z5FQbkFg8ayi6CstJ2jcQfzWnJg`：把**你的机器人/应用加为 base 协作者**（至少 record 读写）。现在只有周君杰的 user identity 在跑。
- IM 汇报：直接发到「创哥, 周君杰」群（oc_5f0f76e254978bce2683517888fba204）即可。

## 6. 接管前请先手动验证

```bash
cd <解压目录>
export TIKHUB_API_KEY=$(grep TIKHUB_API_KEY skills/radar-pull/.env | cut -d= -f2-)
# 1. tikhub 连通（应返回 balance ~9.3）
curl -s -H "Authorization: Bearer $TIKHUB_API_KEY" https://api.tikhub.io/api/v1/tikhub/user/get_user_info | jq .user_data
# 2. benchmark 试跑（不写飞书）
python3 scripts/benchmark_pull.py --dry-run
# 3. 小红书源试跑（应看到 10 词 hits 数）
bash skills/radar-pull/references/tikhub_xhs_keyword.sh | jq 'length'
```

三项 OK → 正式挂 cron，先手动触发一次 radar-pull + 两份日报，结果发群里，我们看到没问题再停周君杰 Mac 那边的旧调度。

## 7. 目录结构

```
topic-radar/
├── skills/radar-pull/           # 09:30 全量拉取
│   ├── SKILL.md                 # 主指令（agent 必读）
│   ├── .env                     # TIKHUB_API_KEY（chmod 600，勿外传）
│   └── references/              # curl/tikhub 直连模板 + 关键词表
├── skills/daily-report-solutions/   # 10:00 方案组日报
├── skills/daily-report-attention/   # 10:10 注意力组日报
├── scripts/benchmark_pull.py    # 10:30 对标账号（独立 skill，挂 radar-pull 节点）
└── TO_HERMES.md                 # 本文件
```

有坑随时在群里 @周君杰。
