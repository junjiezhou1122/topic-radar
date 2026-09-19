#!/bin/bash
# 小红书 AI 关键词全量拉取（10 词）— tikhub 直连版
# 用法: bash references/tikhub_xhs_keyword.sh
# 依赖: TIKHUB_API_KEY（env 或 ../.env）
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
KEYWORDS=("AI编程" "AI工具" "AI Agent" "效率工具" "AI 自动化"
  "Claude Code" "Cursor" "Codex" "OpenClaw" "豆包")
ALL='[]'
for kw in "${KEYWORDS[@]}"; do
  RESP=$(bash "$HERE/tikhub_direct.sh" /api/v1/xiaohongshu/app_v2/search_notes "keyword=$kw" "page=1" 2>/dev/null || echo '{}')
  HITS=$(echo "$RESP" | jq '[(.data.data.items // [])[] | (.note // .) | {
    id: .id,
    title: (.title // ""),
    summary: (.desc // ""),
    link: ("https://www.xiaohongshu.com/explore/" + (.id // "" | tostring)),
    author: (.user.nickname // ""),
    heat: (.liked_count // 0),
    source: "小红书 AI 搜索",
    platform: "小红书",
    signal_type: "🔥 注意力",
    source_item_id: (.id // "" | tostring),
    published_at: ""
  }]' 2>/dev/null || echo '[]')
  ALL=$(jq -s 'add' <(echo "$ALL") <(echo "$HITS"))
  echo "[xhs_search:$kw] $(echo "$HITS" | jq 'length') hits" >&2
done
echo "$ALL"
