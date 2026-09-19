#!/bin/bash
# X 关键词全量拉取（16 个词 × top 10 = ~160 条）
# 用法: bash references/treg_x_keyword.sh
set -e
KEYWORDS=(
  "Claude Code" "Cursor" "Codex" "Copilot" "OpenClaw" "Windsurf"
  "Cline" "MCP" "Computer Use" "AI coding" "AI agent"
  "AI automation" "agentic AI" "AI workflow" "prompt engineering" "AI IDE"
)
ALL='[]'
for kw in "${KEYWORDS[@]}"; do
  RESP=$(/Users/junjie/.local/bin/treg call tikhub.x.twitter-web-fetch-search-timeline --method GET --query "keyword=$kw" --query "search_type=Top" 2>/dev/null || echo '{"data":{"timeline":[]}}')
  HITS=$(echo "$RESP" | jq '[(.data.timeline // [])[] | {
    id: .tweet_id,
    title: (.text[:80]),
    link: ("https://twitter.com/" + (.screen_name // "") + "/status/" + (.tweet_id // "")),
    author: .screen_name,
    heat: (.views // 0),
    source: "X AI 搜索",
    platform: "X",
    signal_type: "🔥 注意力",
    source_item_id: (.tweet_id // "" | tostring),
    published_at: ""
  }]')
  ALL=$(jq -s 'add' <(echo "$ALL") <(echo "$HITS"))
  echo "[x_search:$kw] $(echo "$HITS" | jq 'length') hits" >&2
done
echo "$ALL"
