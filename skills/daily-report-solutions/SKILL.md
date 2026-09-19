# Skill · daily-report-solutions

> 方案组日报：今天的 Show HN + Product Hunt 信号 → AI 筛 → markdown → 飞书 Base 内的 docx block。

## 触发
Multica autopilot，cron `0 10 * * *` (Asia/Shanghai)。**必须晚于 radar-pull 完成。**

## 完整流程（agent 顺序执行）

### Step 1: 拉今日信号
```bash
cd ~/work/topic-radar/skills/daily-report-solutions
python3 scripts/run.py --group solutions --dry-run --date $(date +%Y-%m-%d)
# 应看到 "fetched N signals"
```

### Step 2: agent 自己当 LLM
agent 按 `prompts/solution.md` 的画像 + P0/P1 规则，从 ~15 条一批的候选里出 markdown，写到 `state/recommendations.md`。

- **agent 自己就是 LLM**（不调 treg claude，绕过余额限制）
- 每条必须有：**一句话简介** + **为什么和创哥有关** + 平台 + 标题方向 + 来源
- 目标 20-50 条/天

### Step 3: 写飞书 Base block
```bash
python3 scripts/run.py --group solutions --date $(date +%Y-%m-%d)
```
脚本会：
1. 扫描 Base 内的 block 树
2. 找到/创建 `今日推荐/<日期>/` 文件夹 block
3. 找到/创建 `日报·方案·<日期>` docx block
4. 用 `docs +update --command overwrite` 把 markdown 写入 docx
5. （可选）IM 通知（需要 `im:message.send_as_user` scope）

## 关键路径
- Prompt：`prompts/solution.md`
- State：`state/recommendations.md`（agent 写）
- 脚本：`scripts/run.py`（find-or-create + overwrite 写 Base）
- 飞书 Base：自动管理 `今日推荐/<日期>/日报·方案·<日期>` 路径

## Base 内的最终结构
```
选题雷达 Base
├── 信息流
├── Source Registry
├── 总览
└── 今日推荐 (folder block)
    └── 2026-09-10 (folder block, 每天一个)
        ├── 日报·方案·2026-09-10 (docx block)
        └── 日报·注意力·2026-09-10 (docx block)
```

## 关键设计：幂等
- 同一天多次跑 → 找到现有 block，update 内容，**零新增**
- 新一天跑 → 自动创建新 folder + docx，**不影响历史日期**
- 删除重复 docx 不需要（脚本不会再产生）

## 需要的 lark-cli scope
- ✓ `base:record:read`（拉信号）
- ✓ `drive:drive`（创建 Base 内 block）
- ✓ `docs:document:create`（创建 docx block）
- ✗ `im:message.send_as_user`（缺，需 `lark-cli auth login --scope "im:message.send_as_user"`）

## 失败处理
- fetch 0 条 → 退出码 0，IM 通知"今日无信号"（待加）
- agent 没写 recommendations.md → 报错：先按 prompt 自己跑一遍
- 飞书 API 报错 → 抛出 RuntimeError，cron 任务重试
- 已有同日期 block → 自动 update，不会重名

## 设计原则
- **agent = LLM**：cron 唤醒 agent session，agent 自己执行 LLM 推理 + 写文档
- **一次 LLM 调用 = markdown 报告**，直接产物，不再走 JSON 中间层
- **每条都判断**（不抽样）
- **每条带"为什么和创哥有关"** —— 用户能立刻判断要不要做这个选题
- **基座稳定**：find-or-create 模式 + overwrite 更新 = 永远不会产生重复或野文件