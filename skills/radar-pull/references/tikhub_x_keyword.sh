#!/bin/bash
# X 关键词全量拉取（16 词）— tikhub 直连版
# 用法: bash references/tikhub_x_keyword.sh
# 依赖: TIKHUB_API_KEY（env 或 ../.env）
# 注意: twitter/web 端点当前上游 400（2026-09-19 实测），恢复后即用；失败不阻塞
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
KEYWORDS=("Claude Code" "Cursor" "Codex" "Copilot" "OpenClaw" "Windsurf"
  "Cline" "MCP" "Computer Use" "AI coding" "AI agent"
  "AI automation" "agentic AI" "AI workflow" "prompt engineering" "AI IDE")
ALL='[]'
for kw in "${KEYWORDS[@]}"; do
  RESP=$(bash "$HERE/tikhub_direct.sh" /api/v1/twitter/web/fetch_search_timeline "keyword=$kw" "search_type=Top" 2>/dev/null || echo '{}')
  # 容错：若 twitter/web 上游 400，RESP 会是 {"detail":...}
  HITS=$(echo "$RESP" | jq '[(.data.data.timeline // .data.timeline // [])[] | {
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
  }]' 2>/dev/null || echo '[]')
  ALL=$(jq -s 'add' <(echo "$ALL") <(echo "$HITS"))
  echo "[x_search:$kw] $(echo "$HITS" | jq 'length') hits" >&2
done
echo "$ALL"
