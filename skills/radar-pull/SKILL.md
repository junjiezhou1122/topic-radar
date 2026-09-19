# Skill · radar-pull

> 把外部 6 个信号源全量拉到飞书「信息流表」 (`tblErG6cjYrIcZkv`)。
> agent 自主执行。`references/` 里只有 curl / treg / ego-browser 模板，按需取用或微调。

## 触发
Multica autopilot，cron `30 9 * * *` (Asia/Shanghai)。

## 前置检查
```bash
lark-cli auth status               # user identity 必须 ready
/Users/junjie/.local/bin/treg --version
/Users/junjie/.local/bin/ego-browser --version
```
任何一项失败 → IM 通知用户，等用户处理（blocked）。

## 执行：6 个源（独立运行，单源失败不阻塞其他源）

### 1. Show HN（Solutions）
   参考 `references/curl_showhn.sh`。Algolia `search_by_date` 7 天窗口 + 分页 + `hitsPerPage=1000`，覆盖全天所有 Show HN。
   - curl → 解析 JSON → 提取 `objectID/title/url/author/points/created_at_i` → 入库
   - 如果单页返回 < nbHits，继续翻 `page=1,2,...` 直到凑齐
   - 目标 ≥150 条/天

### 2. Product Hunt（Solutions）
   参考 `references/curl_ph.sh`。RSS feed `https://www.producthunt.com/feed`，全收最新 50 条。
   - curl → XML 解析 → 提取 `id/title/link/content` → 入库
   - 目标 ≥30 条/天（feed 上限 ~50）

### 3. X AI 圈 List（Attention）—— 必须用 ego-browser
   参考 `references/xlist_read.mjs`（直接 `ego-browser nodejs < ...`）。
   - 4 个 list：AI / AI Leaders / AI High Signal / Researcher
   - 每 list 滚动直到连续 2 屏无新文章
   - 输出 `state/xlist_posts.ndjson`（中间产物）
   - 然后 agent 自己 parse ndjson → 入库（不再走 .py）
   - 目标 ≥100 条/天

### 4. X 关键词（Attention）—— 首选 ego-browser 兜底
   参考 `references/ego_x_keyword.mjs`（直接 `ego-browser nodejs < ...`）。
   - 用户已在 ego-browser 登录 X，复用登录态，绕过 treg 计费
   - 关键词列表在 `references/keywords_x.txt`（16 词），每个搜 top 10
   - 输出 `state/ego_x_search.ndjson`，然后 agent 自己 parse + 入库
   - 目标 ≥100 条/天
   - **treg 兜底**：`references/treg_x_keyword.sh`（仅当 ego-browser 不可用时用）

### 5. 小红书 AI 关键词（Attention）—— 首选 ego-browser 兜底
   参考 `references/ego_xhs_keyword.mjs`（直接 `ego-browser nodejs < ...`）。
   - 用户已在 ego-browser 登录小红书
   - 关键词列表在 `references/keywords_xhs.txt`（10 词），每个搜 top 10
   - 输出 `state/ego_xhs_search.ndjson`，agent 自己 parse + 入库
   - 目标 ≥50 条/天
   - **treg 兜底**：`references/treg_xhs_keyword.sh`

### 6. AI 注意力聚合（Aggregate）—— 派生
   agent 自己把今天抓到的所有 X/XHS post 按 `references/topic_map.txt` 映射规则做 topic 聚合：
   - 每个 topic 一条记录：标题=topic, 来源=AI 注意力聚合, dedup=`AI 注意力聚合:{topic}:{today}`
   - 目标 ≥10 条/天（每天能聚合的话题数）

### 7. 对标账号抓取（Benchmark Accounts）—— 独立脚本
   参考 `~/work/topic-radar/scripts/benchmark_pull.py`。
   - 11 个对标账号以 Source Registry (tblTMiv6orSIQ0Ao) 为准，平台 ID 走 `references/benchmark_accounts.json`
   - 默认抓取区间 **智能默认 24h**：
     - 首次跑或 `state/last_run.json` 缺失 → 24h
     - 上次跑在 24h 内 → 24h（不变）
     - 上次跑超过 24h（cron 漏跑）→ `since = min(gap + 1h, 14天)` 自动回溯，补上中间丢失的日期
     - 上限 14 天，避免一次性塞一堆历史
   - 手动 `python3 scripts/benchmark_pull.py [--since-hours N]` 不传 N 则走智能默认
   - 目标 ≥3 条/账号/周
   - 平台适配：
     - 小红书 `tikhub.x.xiaohongshu-app-v2-get-user-posted-notes`
     - B站 `tikhub.x.bilibili-web-fetch-user-post-videos`
     - X `tikhub.x.user.posts`（handle 缺失则跳过该平台）
     - YouTube `scrapecreators.x.v1-youtube-channel-videos`（channel_id 缺失则跳过）
     - 微信公众号 `tikhub.x.wechat-mp-v2-fetch-account-articles`（用 gh_xxx 作为 username）
   - 信号类型 = 🔥 注意力（跟其他 tab 同款卡片）
   - 来源 = 对标账号
   - Dedup Key = `对标账号:<平台>:<原始ID>`
   - 主题 Topic = 账号默认主题（`references/topic_map_duibiao.json`） + 标题关键词叠加
   - 手动/可接 cron：`python3 ~/work/topic-radar/scripts/benchmark_pull.py [--since-hours N]`
   - **评论抓取**（手动开启）：抓帖子后调评论接口，每个帖子取 top 10
     - B站 `tikhub.x.bilibili-web-fetch-video-comments`
     - 小红书 `tikhub.x.xiaohongshu-app-v2-get-note-comments`
     - **不带关键词过滤**——让创哥/agent 自己挑
     - 评论 **嵌入**帖子记录的「评论」字段（长文本，带点赞数/用户名）
     - 重复帖不走 create，走 `+record-batch-update` 只更新「评论」和「抓取时间」
     - 创哥点击帖子详情面板就能看到评论
     - 不再走独立的“问题”tab
   - Dedup Key = `对标账号:<平台>:<原始ID>`
   - 主题 Topic = 账号默认主题（`references/topic_map_duibiao.json`） + 标题关键词叠加

## 去重 + 写飞书
任一源拉完一批后，agent 自己：
```bash
# 1. 读飞书现有 Dedup Key
lark-cli base +record-list --base-token Z5FQbkFg8ayi6CstJ2jcQfzWnJg \
  --table-id tblErG6cjYrIcZkv --field-id "Dedup Key" --as user --limit 2000 \
  --format ndjson --output /tmp/radar_existing.ndjson --overwrite

# 2. 过滤掉已存在的（按来源:原始ID 或 聚合:topic:date）

# 3. 批量写新记录
lark-cli base +record-batch-create --base-token Z5FQbkFg8ayi6CstJ2jcQfzWnJg \
  --table-id tblErG6cjYrIcZkv --json @/tmp/radar_batch.json --as user
```
字段 schema 已在 Base 里定死，参考 `references/record_fields.md`。

## 自检 + 回报
所有 6 个源跑完后：
```bash
lark-cli base +record-list --base-token Z5FQbkFg8ayi6CstJ2jcQfzWnJg \
  --table-id tblErG6cjYrIcZkv --as user --field-id 来源 --field-id 抓取时间 \
  --format ndjson --output /tmp/verify.ndjson --limit 2000

python3 -c "
from collections import Counter
import json
c=Counter(); today='$(date +%Y-%m-%d)'
for l in open('/tmp/verify.ndjson'):
    r=json.loads(l)
    if r.get('抓取时间','').startswith(today):
        c[r.get('来源',[None])[0]]+=1
print(c)"
```
预期：Show HN ≥150, Product Hunt ≥30, X AI 圈 List ≥100, AI 注意力聚合 ≥10。
对标账号是独立脚本，不计入上述自检；单独看 `state/benchmark_posts.ndjson` 增量。

IM 推用户一条：
```
✅ radar-pull 完成 · 2026-09-10
Show HN +0 · PH +0 · X AI List +109 · AI 聚合 +15
（首次跑后增量会更多；后续日常 0 增量 = 幂等成功）
```

## 失败原则
- 任一源失败 → log 跳过，不阻塞其他源
- treg X/XHS 超时/余额不足 → 跳过这俩源，记 warning，IM 通知用户
- lark-cli 报错 → 看 `lark-cli auth status`，必要时引导用户重新登录
- ego-browser 报错（任意场景） → IM 通知用户重新在 ego-browser 登录
- X List ego 报错 → X List 降级为 treg `tikhub.x.twitter-web-fetch-list-timeline`（模板待补）

## 关键路径
- 模板：`references/{curl_showhn.sh, curl_ph.sh, ego_x_keyword.mjs, ego_xhs_keyword.mjs, xlist_read.mjs, xlist_template.sh, treg_x_keyword.sh, treg_xhs_keyword.sh, keywords_x.txt, keywords_xhs.txt, topic_map.txt, record_fields.md, benchmark_accounts.json, topic_map_duibiao.json}`
- 状态：`state/{topic_state.json, xlist_posts.ndjson, benchmark_posts.ndjson}`
- 日志：`~/work/topic-radar/logs/radar-pull/`
- 飞书 Base：`Z5FQbkFg8ayi6CstJ2jcQfzWnJg` / Table `tblErG6cjYrIcZkv`
