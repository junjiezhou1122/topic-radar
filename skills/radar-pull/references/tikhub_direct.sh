#!/bin/bash
# tikhub 直连调用（不经 treg，零路由费）
# 依赖环境变量 TIKHUB_API_KEY（见 ~/.env 或 TO_HERMES.md）
# 用法: bash references/tikhub_direct.sh <api_path> [k=v ...]
# 例:   bash references/tikhub_direct.sh /api/v1/twitter/web/fetch_search_timeline keyword="AI agent" search_type=Top
set -e

if [ -z "$TIKHUB_API_KEY" ]; then
  # 尝试从 skill 目录的 .env 读
  ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env"
  if [ -f "$ENV_FILE" ]; then
    export TIKHUB_API_KEY=$(grep -E '^TIKHUB_API_KEY=' "$ENV_FILE" | cut -d= -f2-)
  fi
fi
if [ -z "$TIKHUB_API_KEY" ]; then
  echo "缺少 TIKHUB_API_KEY（env 或 skill 目录 .env）" >&2
  exit 1
fi

PATH_PART="$1"; shift
QS=""
for kv in "$@"; do
  if [ -n "$QS" ]; then QS="$QS&"; fi
  K="${kv%%=*}"; V="${kv#*=}"
  QS="$QS$K=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$V")"
done
URL="$BASE$PATH_PART"
[ -n "$QS" ] && URL="$URL?$QS"

curl -s --max-time 60 -H "Authorization: Bearer $TIKHUB_API_KEY" "$URL"
