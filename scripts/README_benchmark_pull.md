# benchmark_pull.py — 对标账号抓取

每天抓取 11 个对标账号的新作品，灌进飞书信息流表的 `对标账号` tab（视图 `vewdf9YFf4`）。

## 用法

```bash
python3 ~/work/topic-radar/scripts/benchmark_pull.py [--since-hours N] [--dry-run]
```

参数：
- `--since-hours N`：抓取最近 N 小时内的作品。不传则走智能默认：
  - 首次跑 → 24h
  - 上次跑在 24h 内 → 24h
  - 上次跑超过 24h（cron 漏跑） → 自动回溯补上中间丢失的日期，上限 14 天
- `--dry-run`：只跑抓取+dedup，不写飞书

## 配置文件

- `~/work/topic-radar/skills/radar-pull/references/benchmark_accounts.json`
  11 个账号的平台 ID 映射。要新增/删除账号，直接改这个文件。
- `~/work/topic-radar/skills/radar-pull/references/topic_map_duibiao.json`
  账号默认主题 + 标题关键词叠加规则。

## 平台适配

| 平台 | treg endpoint | 单价 |
|---|---|---|
| 小红书 | `tikhub.x.xiaohongshu-app-v2-get-user-posted-notes` | $0.01 |
| B站 | `tikhub.x.bilibili-web-fetch-user-post-videos` | $0.001 |
| X | `tikhub.x.user.posts` | $0.001 |
| YouTube | `scrapecreators.x.v1-youtube-channel-videos` | $0.00188 |
| 微信公众号 | `tikhub.x.wechat-mp-v2-fetch-account-articles` | $0.01 |

注：X/YouTube 账号的 handle/channel_id 目前还是空（Source Registry 里没填）。
要启用：编辑 `benchmark_accounts.json`，填好对应平台的 `id` 字段。

## 输出

- 中间产物：
  - `~/work/topic-radar/skills/radar-pull/state/benchmark_posts.ndjson`（帖子）
  - `~/work/topic-radar/skills/radar-pull/state/benchmark_comments.ndjson`（评论）
  - `~/work/topic-radar/skills/radar-pull/state/last_run.json`（上次跑时间）
- 飞书信息流表：`Z5FQbkFg8ayi6CstJ2jcQfzWnJg` / `tblErG6cjYrIcZkv`
- 帖子记录带「评论」字段（长文本，top 10 评论嵌入），都在视图 tab `👥 对标账号` (`vewdf9YFf4`)
- 点击任意帖子 → 右侧详情面板可见「评论」字段（带点赞数、用户名）

## Dedup

- 帖子 Dedup Key = `对标账号:<平台>:<原始ID>`
- 再次运行同区间会跳过已存在的记录（幂等）

## 帖子 + 评论同写同取

- 抓帖子后自动调评论接口，每个帖子取 top 10 评论
- **不带关键词过滤**——创哥/agent 自己挑
- 评论作为帖子的「评论」字段嵌入（长文本）
- 重复帖：跳过 create，用 `+record-batch-update` 只更新「评论」和「抓取时间」
- 创哥点击帖子右拉详情面板就能看到评论
- 评论接口支持：B站 / 小红书（公众号/X/YT 暂未接）

## 智能回溯

- 跑完后在 `state/last_run.json` 记录本次完成时间
- 下次跑时检测上次完成时间：gap > 24h 自动用 `gap+1h` 作 since-hours，补上中间丢失
- 但限于 14 天，防止一次性塞进几个月历史

## 接入 cron

Multica autopilot：
```
30 9 * * * cd ~/work/topic-radar && python3 scripts/benchmark_pull.py
```

（radar-pull 的 cron 已经在 `30 9 * * *`，错开几分钟避免争抢 lark-cli token。）

## 待补

- X handle for 张咋啦
- YouTube channel_id for 张咋啦
- 公众号 account `biz` 字段（已加但未使用，目前传 username）
- 字幕/封面等丰富数据：是否要同步写到 作品库对应的账号 table？目前脚本只写信息流，不写作品库。