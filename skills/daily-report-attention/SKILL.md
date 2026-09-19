# Skill · daily-report-attention

> 注意力组日报：今天的 X AI 圈 List + X AI 搜索 + 小红书 AI 搜索 + HN AI 信号 → AI 筛 → markdown → 飞书 Base 内的 docx block。

## 触发
Multica autopilot，cron `10 10 * * *` (Asia/Shanghai)。**必须晚于 radar-pull 完成。**

## 完整流程（agent 顺序执行）

### Step 1: 拉今日信号
```bash
cd ~/work/topic-radar/skills/daily-report-attention
python3 scripts/run.py --group attention --dry-run --date $(date +%Y-%m-%d)
# 应看到 "fetched N signals"
```

### Step 2: agent 自己当 LLM
agent 按 `prompts/attention.md` 的画像 + P0/P1 规则，从 ~15 条一批的候选里出 markdown，写到 `state/recommendations.md`。

- **agent 自己就是 LLM**（不调 treg claude，绕过余额限制）
- 重点关注：同行关注度、时效性、是否能给独立判断
- 每条必须有：**一句话简介** + **为什么和创哥有关** + 平台 + 标题方向 + 来源
- 目标 20-50 条/天

### Step 3: 写飞书 Base block
```bash
python3 scripts/run.py --group attention --date $(date +%Y-%m-%d)
```
脚本会：
1. 扫描 Base 内的 block 树
2. 找到/创建 `今日推荐/<日期>/` 文件夹 block
3. 找到/创建 `日报·注意力·<日期>` docx block
4. 用 `docs +update --command overwrite` 把 markdown 写入 docx
5. （可选）IM 通知

## 关键路径
- Prompt：`prompts/attention.md`
- State：`state/recommendations.md`（agent 写）
- 脚本：`scripts/run.py`（find-or-create + overwrite 写 Base）

## 关键设计：幂等
- 同一天多次跑 → 找到现有 block，update 内容，**零新增**
- 新一天跑 → 自动创建新 folder + docx，**不影响历史日期**
- 删除重复 docx 不需要（脚本不会再产生）

## 与方案组的差异

| 维度 | 方案组 | 注意力组 |
|---|---|---|
| 来源 | Show HN + Product Hunt | X AI 圈 List + X 搜索 + 小红书 + HN AI |
| 选题类型 | 实测/教程 | 趋势/观点/盘点 |
| 推荐门槛 | P0/P1 | P0/P1 + 同行关注度 |
| 每天推荐量 | 20-50 条 | 20-50 条 |

## 设计原则
- **agent = LLM**：cron 唤醒 agent session，agent 自己执行 LLM 推理 + 写文档
- **每条都判断**（不抽样）
- **每条带"为什么和创哥有关"**
- **基座稳定**：find-or-create 模式 + overwrite 更新 = 永远不会产生重复