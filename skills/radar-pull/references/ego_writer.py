#!/usr/bin/env python3
"""把 ego-browser 抓的 ndjson 转成 Base 记录并批量写入。
agent 自跑：python3 references/ego_x_writer.py
"""
import json, os, subprocess, sys
from datetime import datetime, timezone, timedelta

BASE_TOKEN = "Z5FQbkFg8ayi6CstJ2jcQfzWnJg"
TABLE_ID = "tblErG6cjYrIcZkv"
LARK = "/opt/homebrew/bin/lark-cli"
ENV_PATH = "/opt/homebrew/bin:/Users/junjie/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
SKILL_DIR = os.environ.get("SKILL_DIR", "/Users/junjie/work/topic-radar/skills/radar-pull")
CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
NOWSTR = NOW.strftime("%Y-%m-%dT%H:%M:%S+08:00")
TODAY = NOW.strftime("%Y-%m-%d")

# Base select field 限制为这 20 个选项
VALID_TOPICS = {"Computer Use", "AI Coding", "Agent", "MCP", "AI Video", "3D", "Models",
                "AI Tools", "AI 编程", "AI 工具", "AI 新闻", "Coding", "Video", "Research",
                "Productivity", "Creator Tool", "Trending", "Open Source", "Developer Tool", "出海"}

TOPIC_MAP = [
    (["computer use"], "Computer Use"),
    (["mcp"], "MCP"),
    (["claude code", "claude"], "AI Coding"),
    (["cursor"], "AI Coding"),
    (["codex"], "AI Coding"),
    (["copilot"], "AI Coding"),
    (["windsurf"], "AI Coding"),
    (["cline"], "AI Coding"),
    (["ai ide"], "AI Coding"),
    (["ai coding", "ai 编程", "ai编程"], "AI Coding"),
    (["agent"], "Agent"),
    (["openclaw"], "Agent"),
    (["ai automation", "agentic"], "Agent"),
    (["ai video", "sora", "veo", "kling"], "AI Video"),
    (["3d"], "3D"),
    (["gpt", "deepseek", "gemini", "openai", "anthropic", "llm", "大模型", "豆包"], "Models"),
    (["ai tool", "ai app", "ai工具", "ai 工具", "效率工具"], "AI Tools"),
    (["ai workflow", "prompt engineering", "n8n", "zapier", "make"], "Productivity"),
    (["rag", "vector", "embedding", "retrieval"], "Research"),
    (["hardware", "chip", "gpu", "apple silicon", "nvidia", "jetson"], "Developer Tool"),
    (["voice", "whisper", "tts", "speech", "elevenlabs"], "AI 工具"),
    (["training", "fine-tune", "fine tune", "rlhf", "蒸馏", "dpo", "qlora"], "Research"),
    (["open source", "github", "开源"], "Open Source"),
    (["skills", "hooks"], "AI Coding"),
]


def topics(text):
    t = (text or "").lower()
    out = []
    for kws, name in TOPIC_MAP:
        if any(kw in t for kw in kws) and name in VALID_TOPICS and name not in out:
            out.append(name)
    return out


def run(cmd, timeout=180):
    env = os.environ.copy()
    env["PATH"] = ENV_PATH
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def existing_keys():
    tmp = "/tmp/radar_existing.ndjson"
    r = run([LARK, "base", "+record-list",
             "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
             "--field-id", "Dedup Key", "--as", "user", "--limit", "2000",
             "--format", "ndjson", "--output", tmp, "--overwrite"])
    keys = set()
    if os.path.exists(tmp):
        with open(tmp) as f:
            for line in f:
                if line.strip():
                    keys.add(json.loads(line).get("Dedup Key") or "")
    return keys


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(SKILL_DIR, "state", "ego_x_search.ndjson")
    label = sys.argv[2] if len(sys.argv) > 2 else "X AI 搜索"
    platform = sys.argv[3] if len(sys.argv) > 3 else "X"
    if not os.path.exists(src):
        print("no input:", src); return 1
    posts = []
    with open(src) as f:
        for line in f:
            if line.strip():
                posts.append(json.loads(line))
    print(f"loaded {len(posts)} posts from {src}")
    existing = existing_keys()
    records, seen = [], set(existing)
    for p in posts:
        sid = str(p.get("id") or p.get("noteId") or "")
        if not sid:
            continue
        dk = f"{label}:{sid}"
        if dk in seen:
            continue
        seen.add(dk)
        text = p.get("text", "") or p.get("title", "")
        records.append({
            "标题": (text[:80] or dk),
            "摘要": text[:300],
            "链接": p.get("href", ""),
            "作者": p.get("author", ""),
            "发布时间": NOWSTR,
            "抓取时间": NOWSTR,
            "热度": int(p.get("heat", 0) or 0),
            "来源": [label],
            "平台": [platform],
            "信号类型": ["🔥 注意力"],
            "主题 Topic": topics(text),
            "行动状态": ["无"],
            "Dedup Key": dk,
            "Source Item ID": sid,
            "抓取状态": ["正常"],
        })
    print(f"new records (after dedup): {len(records)}")
    if not records:
        return 0
    payload = "/tmp/ego_writer_payload.json"
    with open(payload, "w") as f:
        json.dump({"create_records": records}, f, ensure_ascii=False)
    r = run([LARK, "base", "+record-batch-create",
             "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
             "--json", "@" + payload, "--as", "user"])
    if r.returncode != 0:
        print("lark error:", r.stdout[:500])
        return 1
    data = json.loads(r.stdout)
    inserted = len(data.get("data", {}).get("record_id_list", []))
    print(f"inserted {inserted} records")
    return 0


if __name__ == "__main__":
    sys.exit(main())