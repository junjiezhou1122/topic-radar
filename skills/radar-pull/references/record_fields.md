# 飞书信息流表字段 schema (tblErG6cjYrIcZkv)

写入每条信号记录时使用的字段（顺序与字段 ID 无关，仅作 lark-cli batch-create 的 key）：

| 字段 key | 类型 | 说明 |
|---|---|---|
| 标题 | text | 信号标题（HN/PH 用原文，X/XHS 取 text 截前 80 字） |
| 摘要 | text | 信号摘要（HN 取 story_text 截前 300 字，PH 取 RSS content 截前 300 字） |
| 链接 | text | 原文 URL |
| 作者 | text | 作者名 |
| 发布时间 | datetime | 原始发布时间（YYYY-MM-DDTHH:MM:SS+08:00） |
| 抓取时间 | datetime | 当前抓取时间（YYYY-MM-DDTHH:MM:SS+08:00） |
| 热度 | number | HN points / PH upvotes / X views / XHS likes |
| 增速 Velocity | number | 仅聚合话题用，对比昨日话题热度的百分比变化 |
| 覆盖 Coverage | number | 仅聚合话题用，关联到的话题来源数 |
| 来源 | select | 8 个选项：Show HN / Product Hunt / X AI 搜索 / 小红书 AI 搜索 / X AI 圈 List / AI 注意力聚合 / 对标账号评论 / 对标账号 |
| 平台 | select | X / 小红书 / Hacker News / Product Hunt / 聚合 |
| 信号类型 | select | 🔥 注意力 / 💬 问题 / 🛠 方案 |
| 主题 Topic | multi-select | 8 个选项：Agent / AI Coding / AI Tools / AI Video / Models / MCP / Computer Use / 3D |
| 行动状态 | select | 无 / ⭐收藏 / 🚀已立项 |
| Dedup Key | text | 唯一：`{来源}:{原始ID}` 或 `AI 注意力聚合:{topic}:{YYYY-MM-DD}` |
| Source Item ID | text | 原始 ID（HN objectID / PH Post ID / X tweet_id / XHS note id） |
| 抓取状态 | select | 正常 / 异常 |

## batch-create 用法

```bash
# 1. 把要插入的 records 写到 json 文件
cat > /tmp/radar_batch.json <<'EOF'
{"create_records": [
  {"fields": {
    "标题": "...",
    "摘要": "...",
    ...
    "来源": ["Show HN"],
    "信号类型": ["🛠 方案"],
    "Dedup Key": "Show HN:abc123"
  }},
  ...
]}
EOF

# 2. 调用
lark-cli base +record-batch-create \
  --base-token Z5FQbkFg8ayi6CstJ2jcQfzWnJg \
  --table-id tblErG6cjYrIcZkv \
  --json @/tmp/radar_batch.json --as user
```

select / multi-select 字段的值必须是数组（即使单选）。
