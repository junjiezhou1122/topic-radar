#!/bin/bash
# Multica 一键 setup 脚本
# 前置：用户已经跑了 `multica login` 完成 OAuth 登录
# 用法：
#   1. 在终端跑 `multica login`（会打开浏览器，点同意）
#   2. 等 multica 提示认证成功
#   3. 跑这个脚本

set -e
# multica CLI 路径：优先用 brew 安装的，其次 fallback 到 Multica.app 内嵌
if command -v multica >/dev/null 2>&1; then
  MULTICA="$(command -v multica)"
elif [ -x "/Applications/Multica.app/Contents/Resources/app.asar.unpacked/resources/bin/multica" ]; then
  MULTICA="/Applications/Multica.app/Contents/Resources/app.asar.unpacked/resources/bin/multica"
else
  echo "❌ multica CLI 找不到。请先跑 'curl -fsSL https://raw.githubusercontent.com/multica-ai/multica/main/scripts/install.sh | bash'"
  exit 1
fi
SKILL_DIR="/Users/junjie/work/topic-radar"
AGENT="pi-agent"  # autopilot 用哪个 agent，按你 multica 后台实际名字

echo "=== Step 1: 检查 multica 登录状态 ==="
if ! $MULTICA auth status 2>&1 | grep -q "authenticated\|logged in\|token"; then
  echo "❌ Not logged in. 请先跑 'multica login'，完成浏览器 OAuth 授权"
  exit 1
fi

echo ""
echo "=== Step 2: 启动 daemon ==="
$MULTICA daemon start 2>&1 | head -3 || echo "daemon 可能已启动"

echo ""
echo "=== Step 3: 创建 2 个 skills（radar-pull / daily-report-solutions / daily-report-attention）==="
# 实际上我们不需要把 skills 上传到 multica，因为 autopilot 通过 description 调用 agent，
# agent 读 SKILL.md 就行。但如果 multica 平台需要注册，可以这样：

# Multica skill create 需要 description + content（SKILL.md 全文）
# 但我们暂时不注册 skills —— agent session 会自己读 SKILL.md

echo ""
echo "=== Step 4: 创建 autopilot：radar-pull ==="
PULL_AUTO=$($MULTICA autopilot create \
  --agent "$AGENT" \
  --title "radar-pull" \
  --description "按 ~/work/topic-radar/skills/radar-pull/SKILL.md 跑 6 个源的 pull：Show HN (curl)、Product Hunt (curl)、X AI 圈 List (ego-browser)、X 关键词 (ego-browser 兜底)、小红书关键词 (ego-browser 兜底)、AI 注意力聚合 (派生)。完成后向 /tmp/radar_ims/ 写一条 IM 摘要。" \
  --mode run_only \
  --output json 2>&1 | tee /tmp/pull_auto.json | python3 -c "
import json, sys
data = sys.stdin.read()
print(data)
try:
    d = json.loads(data)
    if d.get('id'): print(f'AUTOPILOT_ID={d[\"id\"]}', file=sys.stderr)
except: pass
")
PULL_ID=$(echo "$PULL_AUTO" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('id',''))" 2>/dev/null)
echo "  radar-pull autopilot id: $PULL_ID"

echo ""
echo "=== Step 5: 给 radar-pull 加 cron 触发：每天 09:30 ==="
$MULTICA autopilot trigger-add "$PULL_ID" \
  --kind schedule \
  --cron "30 9 * * *" \
  --timezone "Asia/Shanghai" 2>&1 | head -3

echo ""
echo "=== Step 6: 创建 autopilot：daily-report-solutions ==="
SOL_AUTO=$($MULTICA autopilot create \
  --agent "$AGENT" \
  --title "daily-report-solutions" \
  --description "按 ~/work/topic-radar/skills/daily-report-solutions/SKILL.md 跑：拉今日 Show HN + Product Hunt → 自己当 LLM 按 prompts/solution.md 筛 → 写 state/recommendations.md → 跑 scripts/run.py 把 docx 写到飞书 Base 今日推荐/<日期>/日报·方案·<日期>。" \
  --mode run_only \
  --output json 2>&1)
SOL_ID=$(echo "$SOL_AUTO" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('id',''))" 2>/dev/null)
echo "  daily-report-solutions autopilot id: $SOL_ID"

echo ""
echo "=== Step 7: 给 solutions 加 cron：每天 10:00 ==="
$MULTICA autopilot trigger-add "$SOL_ID" \
  --kind schedule \
  --cron "0 10 * * *" \
  --timezone "Asia/Shanghai" 2>&1 | head -3

echo ""
echo "=== Step 8: 创建 autopilot：daily-report-attention ==="
ATT_AUTO=$($MULTICA autopilot create \
  --agent "$AGENT" \
  --title "daily-report-attention" \
  --description "按 ~/work/topic-radar/skills/daily-report-attention/SKILL.md 跑：拉今日 X AI 圈 List + X 搜索 + 小红书 + HN AI → 自己当 LLM 按 prompts/attention.md 筛 → 写 state/recommendations.md → 跑 scripts/run.py 写到飞书 Base 今日推荐/<日期>/日报·注意力·<日期>。" \
  --mode run_only \
  --output json 2>&1)
ATT_ID=$(echo "$ATT_AUTO" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('id',''))" 2>/dev/null)
echo "  daily-report-attention autopilot id: $ATT_ID"

echo ""
echo "=== Step 9: 给 attention 加 cron：每天 10:10 ==="
$MULTICA autopilot trigger-add "$ATT_ID" \
  --kind schedule \
  --cron "10 10 * * *" \
  --timezone "Asia/Shanghai" 2>&1 | head -3

echo ""
echo "=== Step 10: 创建 autopilot：benchmark-pull ==="
BENCH_AUTO=$($MULTICA autopilot create \
  --agent "$AGENT" \
  --title "benchmark-pull" \
  --description "按 ~/work/topic-radar/scripts/benchmark_pull.py 跑（不传 --since-hours，走智能默认 24h）：拉 11 个对标账号（何同学、影视飓风、张咋啦、直男山禾、AI超元域、卡尔的AI沃茨、数字生命卡兹克、秋芝2046、Xuan酱、木子不写代码、神烦老狗）最近的新作品，Dedup 后灌入飞书信息流表（Z5FQbkFg8ayi6CstJ2jcQfzWnJg / tblErG6cjYrIcZkv）。X/YouTube handle 未填则 skip。脚本会在 ~/work/topic-radar/skills/radar-pull/state/im_report.txt 生成摘要，agent 读完后再用 lark-cli im +send 推一条 IM。" \
  --mode run_only \
  --output json 2>&1)
BENCH_ID=$(echo "$BENCH_AUTO" | python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('id',''))" 2>/dev/null)
echo "  benchmark-pull autopilot id: $BENCH_ID"

echo ""
echo "=== Step 11: 给 benchmark-pull 加 cron：每天 10:30 ==="
$MULTICA autopilot trigger-add "$BENCH_ID" \
  --kind schedule \
  --cron "30 10 * * *" \
  --timezone "Asia/Shanghai" 2>&1 | head -3

echo ""
echo "=== Step 12: 列出所有 autopilot ==="
$MULTICA autopilot list --output pretty 2>&1 | head -30

echo ""
echo "✅ Setup complete!"
echo "  - radar-pull: 09:30 daily"
echo "  - daily-report-solutions: 10:00 daily"
echo "  - daily-report-attention: 10:10 daily"
echo "  - benchmark-pull: 10:30 daily"