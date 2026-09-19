#!/bin/bash
# 小红书 AI 关键词全量拉取（10 个词 × top 10 = ~100 条）
# 用法: bash references/treg_xhs_keyword.sh
set -e
KEYWORDS=(
  "AI编程" "AI工具" "AI Agent" "效率工具" "AI 自动化"
  "Claude Code" "Cursor" "Codex" "OpenClaw" "豆包"
)
ALL='[]'
for kw in "${KEYWORDS[@]}"; do
  RESP=$(/Users/junjie/.local/bin/treg call tikhub.x.xiaohongshu-app-v2-search-notes --method GET --query "keyword=$kw" 2>/dev/null || echo '{"data":{"data":{"items":[]}}}')
  HITS=$(echo "$RESP" | jq '[((.data.data.items // [])[:10])[] | {
    id: .note.id,
    title: (.note.title // ""),
    summary: (.note.desc // ""),
    link: ("https://www.xiaohongshu.com/explore/" + (.note.id // "" | tostring)),
    author: (.note.user.nickname // ""),
    heat: (.note.liked_count // 0),
    source: "小红书 AI 搜索",
    platform: "小红书",
    signal_type: "🔥 注意力",
    source_item_id: (.note.id // "" | tostring),
    published_at: ""
  }]')
  ALL=$(jq -s 'add' <(echo "$ALL") <(echo "$HITS"))
  echo "[xhs_search:$kw] $(echo "$HITS" | jq 'length') hits" >&2
done
echo "$ALL"
