#!/bin/bash
# X AI 圈 List 全量拉取（4 个 list）— tikhub 直连版
# 用法: bash references/tikhub_x_list.sh
# 依赖: TIKHUB_API_KEY（env 或 ../.env）
# 注意: twitter/web 端点当前上游 400（2026-09-19 实测），恢复后即用
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
# list_id 来自 data/lists/x/*.json（content-intelligence-system 的稳定 list 清单）
LISTS=(
  "2096881905236926777:AI同行博主"
  # ↓ 其余 3 个 list_id 从这里补：data/lists/x/{ai_news_radar,agent_automation,ai_kol_researcher}.json 的 list_url
)
ALL='[]'
for entry in "${LISTS[@]}"; do
  LID="${entry%%:*}"; LNAME="${entry#*:}"
  RESP=$(bash "$HERE/tikhub_direct.sh" /api/v1/twitter/web/fetch_list_timeline "list_id=$LID" 2>/dev/null || echo '{}')
  HITS=$(echo "$RESP" | jq --arg ln "$LNAME" '[(.data.data.timeline // .data.timeline // [])[] | {
    id: .tweet_id,
    title: (.text[:80]),
    link: ("https://twitter.com/" + (.screen_name // "") + "/status/" + (.tweet_id // "")),
    author: .screen_name,
    heat: (.views // 0),
    source: ("X AI 圈 List(" + $ln + ")"),
    platform: "X",
    signal_type: "🔥 注意力",
    source_item_id: (.tweet_id // "" | tostring),
    published_at: ""
  }]' 2>/dev/null || echo '[]')
  ALL=$(jq -s 'add' <(echo "$ALL") <(echo "$HITS"))
  echo "[x_list:$LNAME] $(echo "$HITS" | jq 'length') hits" >&2
done
echo "$ALL"
