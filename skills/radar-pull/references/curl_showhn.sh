#!/bin/bash
# Show HN 全量拉取（7 天窗口，hitsPerPage=1000，分页）
# 用法: bash references/curl_showhn.sh
set -e
SINCE=$(($(date +%s) - 7*86400))
ALL='[]'
PAGE=0
TOTAL=null
while [ "$TOTAL" = "null" ] || [ "$(echo "$ALL" | jq 'length')" -lt "$TOTAL" ] && [ "$PAGE" -lt 10 ]; do
  RESP=$(curl -sL --max-time 60 "https://hn.algolia.com/api/v1/search_by_date?tags=show_hn&hitsPerPage=1000&page=$PAGE&numericFilters=created_at_i%3E$SINCE")
  TOTAL=$(echo "$RESP" | jq '.nbHits')
  ALL=$(jq -s 'add' <(echo "$ALL") <(echo "$RESP" | jq '.hits'))
  PAGE=$((PAGE+1))
  echo "[showhn] page $PAGE, total collected: $(echo "$ALL" | jq 'length') / $TOTAL" >&2
done
echo "$ALL" | jq '[.[] | {
  id: .objectID,
  title: .title,
  link: (.url // ("https://news.ycombinator.com/item?id=" + .objectID)),
  author: .author,
  heat: (.points // 0),
  source: "Show HN",
  platform: "Hacker News",
  signal_type: "🛠 方案",
  source_item_id: .objectID,
  published_at: (.created_at // "")
}]'
