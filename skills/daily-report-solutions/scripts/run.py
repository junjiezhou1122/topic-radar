#!/usr/bin/env python3
"""daily-report 完整执行脚本（Base block 路线）

流程：
1. 拉今日信号（从 Base 信息流表）
2. 读 agent 写的 state/recommendations.md
3. 在 Base 内的 今日推荐/<日期>/ 下找到或创建 docx block，把内容写入
4. （可选）飞书 IM 通知

幂等：同一天多次跑会 update 已有的 docx，不会创建重复

用法：
    python3 scripts/run.py --group solutions --date 2026-09-10
    python3 scripts/run.py --group attention --date 2026-09-10
"""
import argparse, json, os, subprocess, sys
from datetime import datetime, timezone, timedelta

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_TOKEN = "Z5FQbkFg8ayi6CstJ2jcQfzWnJg"
TABLE_ID = "tblErG6cjYrIcZkv"
LARK = "/opt/homebrew/bin/lark-cli"
ENV_PATH = "/opt/homebrew/bin:/Users/junjie/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
CST = timezone(timedelta(hours=8))

# 根目录 block id：选题雷达 Base 内的"今日推荐"folder block
# （首次跑会通过 list 自动查找/创建，不需要硬编码）
ROOT_RECS_NAME = "今日推荐"

SOURCES = {
    "solutions": ("Show HN", "Product Hunt"),
    "attention": ("X AI 圈 List", "X AI 搜索", "小红书 AI 搜索", "HN AI"),
    "aggregate": ("AI 注意力聚合",),
}
GROUP_NAMES = {"solutions": "方案", "attention": "注意力", "aggregate": "聚合"}


def run(cmd, timeout=180):
    env = os.environ.copy()
    env["PATH"] = ENV_PATH
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def fetch_signals(target_date, sources):
    next_day = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    filter_json = {
        "logic": "and",
        "conditions": [
            ["来源", "intersects", list(sources)],
            ["抓取时间", ">", "ExactDate(%s 00:00:00)" % target_date],
            ["抓取时间", "<", "ExactDate(%s 00:00:00.001)" % next_day],
        ]
    }
    with open("/tmp/dr_filter.json", "w") as f:
        json.dump(filter_json, f, ensure_ascii=False)
    tmp = "/tmp/dr_signals.ndjson"
    r = run([LARK, "base", "+record-list",
             "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
             "--field-id", "标题", "--field-id", "摘要", "--field-id", "链接",
             "--field-id", "热度", "--field-id", "来源", "--field-id", "record_id",
             "--field-id", "主题 Topic",
             "--filter-json", "@/tmp/dr_filter.json",
             "--as", "user", "--limit", "500",
             "--format", "ndjson", "--output", tmp, "--overwrite"])
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError("fetch failed: %s" % r.stdout[:300])
    rows = []
    if os.path.exists(tmp):
        with open(tmp) as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


def list_all_blocks():
    """获取 Base 内所有 block（含嵌套），用 parent_id 索引"""
    r = run([LARK, "base", "+base-block-list", "--base-token", BASE_TOKEN, "--as", "user"])
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError("list blocks failed: %s" % r.stdout[:300])
    d = json.loads(r.stdout)
    return d.get("data", {}).get("blocks", [])


def find_block(blocks, name, parent_id):
    """Find a block by name and parent_id"""
    for b in blocks:
        if b.get("name") == name and b.get("parent_id") == parent_id:
            return b
    return None


def find_or_create_root_recs_folder(blocks):
    """找到或创建 Base 内的 今日推荐 folder block"""
    root_blocks = [b for b in blocks if not b.get("parent_id")]
    existing = find_block(root_blocks, ROOT_RECS_NAME, None)
    if existing:
        return existing["id"]
    r = run([LARK, "base", "+base-block-create",
             "--base-token", BASE_TOKEN,
             "--type", "folder",
             "--name", ROOT_RECS_NAME,
             "--as", "user"])
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError("create root folder failed: %s" % r.stdout[:300])
    d = json.loads(r.stdout)
    new_id = d["data"]["block"]["id"]
    print(f"  + created root folder: {ROOT_RECS_NAME} ({new_id})")
    return new_id


def find_or_create_date_folder(blocks, parent_id, date_str):
    """找到或创建 Base 内的 <日期> folder block"""
    children = [b for b in blocks if b.get("parent_id") == parent_id]
    existing = find_block(children, date_str, parent_id)
    if existing:
        return existing["id"]
    r = run([LARK, "base", "+base-block-create",
             "--base-token", BASE_TOKEN,
             "--type", "folder",
             "--name", date_str,
             "--parent-id", parent_id,
             "--as", "user"])
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError("create date folder failed: %s" % r.stdout[:300])
    d = json.loads(r.stdout)
    new_id = d["data"]["block"]["id"]
    print(f"  + created date folder: {date_str} ({new_id})")
    return new_id


def find_or_create_doc_block(blocks, parent_id, title):
    """找到或创建 docx block"""
    children = [b for b in blocks if b.get("parent_id") == parent_id]
    existing = find_block(children, title, parent_id)
    if existing:
        return existing["id"], existing.get("docx_token")
    r = run([LARK, "base", "+base-block-create",
             "--base-token", BASE_TOKEN,
             "--type", "docx",
             "--name", title,
             "--parent-id", parent_id,
             "--as", "user"])
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError("create doc block failed: %s" % r.stdout[:300])
    d = json.loads(r.stdout)
    new_id = d["data"]["block"]["id"]
    new_token = d["data"]["block"].get("docx_token")
    print(f"  + created doc block: {title} ({new_id}, docx={new_token})")
    return new_id, new_token


def write_doc_content(docx_token, markdown, title):
    """把 markdown 写入 docx（overwrite 模式）"""
    tmp = "/tmp/dr_doc.md"
    with open(tmp, "w") as f:
        f.write(markdown)
    r = run([LARK, "docs", "+update",
             "--doc", docx_token,
             "--doc-format", "markdown",
             "--command", "overwrite",
             "--content", "@" + tmp,
             "--as", "user"])
    if r.returncode != 0 or '"ok": false' in r.stdout:
        raise RuntimeError("doc update failed: %s" % r.stdout[:300])
    return json.loads(r.stdout)["data"]


def notify(url, group_name, total, n_rec):
    chat = os.environ.get("NOTIFY_CHAT")
    if not chat:
        return
    msg = f"📊 {group_name}组日报已生成\n· 看 {total} 条 → 推荐 {n_rec} 条\n· 文档：{url}"
    run([LARK, "im", "+messages-send", "--chat-id", chat, "--text", msg, "--as", "user"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", required=True, choices=["solutions", "attention", "aggregate"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    now = datetime.now(CST)
    target = a.date or now.strftime("%Y-%m-%d")
    sources = SOURCES[a.group]
    group_name = GROUP_NAMES[a.group]

    print(f"=== daily-report {a.group} for {target} ===")

    # Step 1: fetch
    rows = fetch_signals(target, sources)
    print(f"  fetched {len(rows)} signals")
    if a.dry_run:
        return 0

    # Step 2: agent must have written markdown
    state = os.path.join(SKILL_DIR, "state", "recommendations.md")
    if not os.path.exists(state):
        print(f"  ERROR: {state} missing — agent should produce this via LLM first")
        return 1
    with open(state) as f:
        markdown = f.read()
    print(f"  read markdown: {len(markdown)} chars")

    # Step 3: navigate Base block tree
    print("  scanning Base blocks...")
    blocks = list_all_blocks()
    root_id = find_or_create_root_recs_folder(blocks)
    print(f"  root '{ROOT_RECS_NAME}': {root_id}")
    date_id = find_or_create_date_folder(blocks, root_id, target)
    print(f"  date folder '{target}': {date_id}")

    title = f"日报·{group_name}·{target}"
    block_id, docx_token = find_or_create_doc_block(blocks, date_id, title)
    print(f"  doc block '{title}': {block_id} (docx={docx_token})")

    # Step 4: write content
    result = write_doc_content(docx_token, markdown, title)
    url = result.get("document", {}).get("url", f"https://xinyouduzhong.feishu.cn/docx/{docx_token}")
    print(f"  doc updated: {url}")

    # Step 5: IM
    n_rec = markdown.count("###")
    notify(url, group_name, len(rows), n_rec)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        print(f"FATAL: {ex}", file=sys.stderr)
        sys.exit(1)