#!/bin/bash
# X AI 圈列表 → 飞书 一条命令（agent 启动模板，可按需改）
# 用法: bash references/xlist_template.sh
set -e
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/Users/junjie/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

echo "== [1/2] 刷 X 列表（ego-browser 必须已登录你的推特）=="
/Users/junjie/.local/bin/ego-browser nodejs < "$SKILL_DIR/references/xlist_read.mjs"

echo "== [2/2] agent 自己 parse ndjson + 写飞书 =="
echo "→ 读 $SKILL_DIR/state/xlist_posts.ndjson"
echo "→ 调 lark-cli base +record-batch-create"
echo "→ 去重键 = X AI 圈 List:{tweet_id}"
echo "（这一步 agent 自己跑，不再用 .py）"
echo "== 完成 =="
