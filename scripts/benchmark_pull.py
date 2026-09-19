#!/usr/bin/env python3
"""对标账号抓取脚本 — 信息流 Source7

输入：
- references/benchmark_accounts.json（11 个账号的平台 ID 映射）
- references/topic_map_duibiao.json（默认主题 + 关键词叠加）

输出：
- NDJSON 写到 state/benchmark_posts.ndjson（中间产物）
- Dedup 后批量写飞书信息流表（Z5FQbkFg8ayi6CstJ2jcQfzWnJg / tblErG6cjYrIcZkv）

用法：
    python3 scripts/benchmark_pull.py [--since-hours N] [--dry-run]

平台适配：
    小红书   tikhub.x.xiaohongshu-app-v2-get-user-posted-notes
    B站      tikhub.x.bilibili-web-fetch-user-post-videos
    X        tikhub.x.user.posts
    YouTube  scrapecreators.x.v1-youtube-channel-videos
    微信公众号  tikhub.x.wechat-mp-v2-fetch-account-articles

去重 key: 对标账号:<平台>:<账号名>:<作品ID>
信号类型: 🔥 注意力（让卡片跟其他 tab 长得一样）

依赖:
    /Users/junjie/.local/bin/treg
    lark-cli
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "radar-pull"
ACCOUNTS_PATH = SKILL_DIR / "references" / "benchmark_accounts.json"
TOPIC_MAP_PATH = SKILL_DIR / "references" / "topic_map_duibiao.json"
STATE_DIR = SKILL_DIR / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)
LAST_RUN_PATH = STATE_DIR / "last_run.json"

# 默认只看最近 24h，但如果上次跑超过 24h（cron 漏跑），自动回溯到“上次跑 + 1h buffer”
# 防止漏跑后丢掉中间那天的作品
DEFAULT_SINCE_HOURS = 24
BACKFILL_BUFFER_HOURS = 1
MAX_BACKFILL_HOURS = 24 * 14  # 上限 14 天，避免一次性塞进一堆历史

TREG = "/Users/junjie/.local/bin/treg"
LARK_BASE_TOKEN = "Z5FQbkFg8ayi6CstJ2jcQfzWnJg"
LARK_TABLE_ID = "tblErG6cjYrIcZkv"

# 11 个账号都视为「对标账号」信号类型，跟其他 tab 卡片同款
SIGNAL_TYPE = "🔥 注意力"

CST = timezone(timedelta(hours=8))


# ---------- tikhub 直连路由（2026-09-19 起默认，零 treg 路由费） ----------
# 说明：treg 的服务端仍持有同一把 tikhub key，但每次调用收 ~$0.001-0.002 路由费。
# 现在直接用 TIKHUB_API_KEY 打 api.tikhub.io，余额不足/未登录 treg 的机器也能跑。
TIKHUB_ENDPOINT_MAP = {
    "tikhub.x.xiaohongshu-app-v2-get-user-posted-notes": ("GET", "/api/v1/xiaohongshu/app_v2/get_user_posted_notes"),
    "tikhub.x.xiaohongshu-app-v2-get-note-comments": ("GET", "/api/v1/xiaohongshu/app_v2/get_note_comments"),
    "tikhub.x.bilibili-web-fetch-user-post-videos": ("GET", "/api/v1/bilibili/web/fetch_user_post_videos"),
    "tikhub.x.bilibili-web-fetch-video-comments": ("GET", "/api/v1/bilibili/web/fetch_video_comments"),
    "tikhub.x.user.posts": ("GET", "/api/v1/twitter/web/fetch_user_post_tweet"),
    "tikhub.x.wechat-mp-v2-fetch-account-articles": ("POST", "/api/v1/wechat_mp/v2/fetch_account_articles"),
    "__youtube_channel_videos__": ("GET", "/api/v1/youtube/web_v2/get_channel_videos"),
}
TIKHUB_BASE = "https://api.tikhub.io"


def _find_tikhub_key() -> str:
    v = os.environ.get("TIKHUB_API_KEY", "").strip()
    if v:
        return v
    env_file = ROOT / "skills" / "radar-pull" / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("TIKHUB_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


def tikhub_call(endpoint, method="GET", query=None, data=None, timeout=60):
    """tikhub 直连。query 形如 "a=1&b=2"（treg 风格），自动转成 URL params。"""
    key = _find_tikhub_key()
    if not key:
        print("[tikhub FAIL] 缺少 TIKHUB_API_KEY", file=sys.stderr)
        return None
    _, path = TIKHUB_ENDPOINT_MAP[endpoint]
    # treg 风格参数名 → tikhub 实际参数名
    if endpoint == "tikhub.x.user.posts" and query:
        query = query.replace("handle=", "screen_name=", 1)
    headers = ["Authorization: Bearer " + key]
    body = None
    url = TIKHUB_BASE + path
    if method == "GET":
        if query:
            url += "?" + query
    else:
        body = json.dumps(data or {}, ensure_ascii=False)
        headers.append("Content-Type: application/json")
    cmd = ["curl", "-s", "--max-time", str(timeout), url]
    for h in headers:
        cmd += ["-H", h]
    if body:
        cmd += ["-d", body]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 10)
    if r.returncode != 0:
        print(f"[tikhub FAIL] {endpoint}: {r.stderr[:200]}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"[tikhub JSON FAIL] {endpoint}: {e}", file=sys.stderr)
        return None


def treg_call(endpoint, method="GET", query=None, data=None, timeout=30):
    """tikhub 系端点直连；其余（scrapecreators 等）回退 treg。"""
    if endpoint in TIKHUB_ENDPOINT_MAP:
        return tikhub_call(endpoint, method=method, query=query, data=data, timeout=timeout)
    cmd = [TREG, "call", endpoint, "--method", method]
    if query:
        cmd += ["--query", query]
    if data:
        cmd += ["--data", json.dumps(data, ensure_ascii=False)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        print(f"[treg MISSING] {endpoint}: treg CLI 不存在，跳过", file=sys.stderr)
        return None
    if r.returncode != 0:
        print(f"[treg FAIL] {endpoint}: {r.stderr[:200]}", file=sys.stderr)
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"[treg JSON FAIL] {endpoint}: {e}", file=sys.stderr)
        return None


# ---------- 平台适配器 ----------
class SkipPlatform(Exception):
    """未配置 ID、主动跳过的平台。不当错误处理，只在 stats 记 'skip'。"""
    pass


# 评论抓取默认最多 top N 条（过多会淹没信号）
MAX_COMMENTS_PER_POST = 30
BILI_PAGE_SIZE = 30
XHS_PAGE_SIZE = 30
MAX_PAGES = 3  # 最多翻 3 页，避免爆款帖子拉太多


def fetch_bilibili_comments(bvid, limit=MAX_COMMENTS_PER_POST):
    """B站：拿指定视频的 top 评论，带翻页。不带关键词过滤——让下游 agent / 创哥自己挑。"""
    out = []
    for page in range(1, MAX_PAGES + 1):
        if len(out) >= limit:
            break
        resp = treg_call(
            "tikhub.x.bilibili-web-fetch-video-comments",
            query=f"bv_id={bvid}&page={page}&page_size={BILI_PAGE_SIZE}",
        )
        if not resp:
            break
        replies = (((resp.get("data") or {}).get("data") or {}).get("replies")) or []
        if not replies:
            break
        for r in replies:
            if len(out) >= limit:
                break
            if not isinstance(r, dict):
                continue
            msg = (r.get("content") or {}).get("message", "") or ""
            if not msg:
                continue
            like = int(r.get("like") or 0)
            uname = (r.get("member") or {}).get("uname", "") or ""
            rpid = str(r.get("rpid") or "")
            out.append({
                "platform": "B站",
                "comment_id": rpid,
                "text": msg,
                "likes": like,
                "user": uname,
                "link": f"https://www.bilibili.com/video/{bvid}#reply{rpid}",
            })
        # 判断是否还有更多
        page_info = (((resp.get("data") or {}).get("data") or {}).get("page") or {})
        total = int(page_info.get("count") or 0)
        if total <= page * BILI_PAGE_SIZE:
            break
    return out


def fetch_xiaohongshu_comments(note_id, limit=MAX_COMMENTS_PER_POST):
    """小红书：拿指定笔记的 top 评论，带 cursor 翻页。不带关键词过滤。"""
    out = []
    cursor = None  # None = 不传 cursor 参数；传 "" 会让 API 返回 0 条
    for _ in range(MAX_PAGES):
        if len(out) >= limit:
            break
        if cursor is None:
            query = f"note_id={note_id}"
        else:
            query = f"note_id={note_id}&cursor={cursor}"
        resp = treg_call(
            "tikhub.x.xiaohongshu-app-v2-get-note-comments",
            query=query,
        )
        if not resp:
            break
        data = (((resp.get("data") or {}).get("data")) or {})
        cs = data.get("comments") or []
        if not cs:
            break
        for c in cs:
            if len(out) >= limit:
                break
            if not isinstance(c, dict):
                continue
            msg = c.get("content") or ""
            if not msg:
                continue
            like = int(c.get("like_count") or 0)
            nick = (c.get("user") or {}).get("nickname", "") or ""
            cid = str(c.get("id") or c.get("comment_id") or "")
            out.append({
                "platform": "小红书",
                "comment_id": cid,
                "text": msg,
                "likes": like,
                "user": nick,
                "link": f"https://www.xiaohongshu.com/explore/{note_id}",
            })
        if not data.get("has_more"):
            break
        cursor_raw = data.get("cursor")
        if isinstance(cursor_raw, dict):
            cursor = cursor_raw.get("cursor", "") or ""
        elif isinstance(cursor_raw, str):
            import json as _j
            try:
                cursor = _j.loads(cursor_raw).get("cursor", "") or ""
            except Exception:
                cursor = ""
        if not cursor:
            break
    return out


COMMENT_FETCHERS = {
    "B站": lambda plat, sid: fetch_bilibili_comments(sid),
    "小红书": lambda plat, sid: fetch_xiaohongshu_comments(sid),
}


def fetch_xiaohongshu(user_id, since_hours=24*7):
    """小红书：get_user_posted_notes 返回用户已发笔记。"""
    resp = treg_call(
        "tikhub.x.xiaohongshu-app-v2-get-user-posted-notes",
        query=f"user_id={user_id}",
    )
    if not resp:
        return []
    notes = (((resp.get("data") or {}).get("data") or {}).get("notes")) or []
    items = []
    for n in notes:
        if not isinstance(n, dict):
            continue
        note_id = str(n.get("id") or n.get("note_id") or "")
        if not note_id:
            continue
        ts_ms = n.get("create_time") or n.get("time") or n.get("last_update_time") or 0
        # 小红书 time 是 ms 时间戳
        try:
            ts_int = int(ts_ms)
            ts = ts_int / 1000 if ts_int > 10**12 else ts_int
        except (TypeError, ValueError):
            ts = 0
        dt = datetime.fromtimestamp(ts, tz=CST).strftime("%Y-%m-%dT%H:%M:%S+08:00") if ts else ""
        items.append({
            "platform": "小红书",
            "source_item_id": note_id,
            "title": (n.get("display_title") or n.get("title") or n.get("desc") or "").strip()[:80],
            "summary": (n.get("desc") or "")[:300],
            "link": f"https://www.xiaohongshu.com/explore/{note_id}",
            "heat": int(n.get("likes") or n.get("liked_count") or 0),
            "published_at": dt,
            "author_raw": (n.get("user") or {}).get("nickname") or "",
            "dedup_key": f"对标账号:小红书:{note_id}",
        })
    return items


def fetch_bilibili(uid, since_hours=24*7):
    """B站：fetch_user_post_videos 拿用户最新投稿。"""
    resp = treg_call(
        "tikhub.x.bilibili-web-fetch-user-post-videos",
        query=f"uid={uid}",
    )
    if not resp:
        return []
    data = (resp.get("data") or {}).get("data") or {}
    vlist_raw = data.get("list") or data.get("vlist") or {}
    if isinstance(vlist_raw, dict):
        vlist = vlist_raw.get("vlist") or []
    elif isinstance(vlist_raw, list):
        vlist = vlist_raw
    else:
        vlist = []
    items = []
    for v in vlist:
        if not isinstance(v, dict):
            continue
        bvid = v.get("bvid") or ""
        aid = str(v.get("aid") or "")
        sid = bvid or aid
        if not sid:
            continue
        ts = int(v.get("created") or 0)
        dt = datetime.fromtimestamp(ts, tz=CST).strftime("%Y-%m-%dT%H:%M:%S+08:00") if ts else ""
        items.append({
            "platform": "B站",
            "source_item_id": sid,
            "title": (v.get("title") or "").strip()[:80],
            "summary": (v.get("description") or "")[:300],
            "link": f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}",
            "heat": int(v.get("like") or 0),
            "published_at": dt,
            "author_raw": v.get("author") or "",
            "dedup_key": f"对标账号:B站:{sid}",
        })
    return items


def fetch_x(handle, since_hours=24*7):
    """X: tikhub.x.user.posts by handle。handle 为空 → skip。"""
    if not handle:
        raise SkipPlatform("X handle 未填，跳过")
    resp = treg_call(
        "tikhub.x.user.posts",
        query=f"handle={handle}",
    )
    if not resp:
        return []
    tl = (((resp.get("data") or {}).get("data") or {}).get("timeline") or [])
    items = []
    for tw in tl:
        tid = str(tw.get("tweet_id") or tw.get("rest_id") or "")
        if not tid:
            continue
        ts_ms = int(tw.get("created_at") or 0)
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=CST).strftime("%Y-%m-%dT%H:%M:%S+08:00") if ts_ms else ""
        items.append({
            "platform": "X",
            "source_item_id": tid,
            "title": (tw.get("text") or "")[:80],
            "summary": (tw.get("text") or "")[:300],
            "link": f"https://x.com/i/status/{tid}",
            "heat": int((tw.get("views") or {}).get("count") or 0),
            "published_at": dt,
            "author_raw": "",
            "dedup_key": f"对标账号:X:{tid}",
        })
    return items


def fetch_youtube(channel_id, since_hours=24*7):
    """YouTube：tikhub /youtube/web_v2/get_channel_videos（直连，无需 treg）。
    注意：tikhub 返回的 published_time 是相对文本（如 "2 days ago"），无精确时间戳，
    不做 since_hours 过滤，靠飞书侧 dedup_key 保证幂等。channel_id 为空 → skip。"""
    if not channel_id:
        raise SkipPlatform("YouTube channel_id 未填，跳过")
    resp = tikhub_call(
        "__youtube_channel_videos__",
        query=f"channel_id={channel_id}",
    )
    if not resp:
        return []
    inner = ((resp.get("data") or {}).get("data") or resp.get("data") or {})
    arr = inner.get("videos") or []
    if isinstance(arr, dict):
        arr = arr.get("videos") or []
    items = []
    for v in arr:
        vid = v.get("video_id") or v.get("id") or ""
        if not vid:
            continue
        items.append({
            "platform": "YouTube",
            "source_item_id": vid,
            "title": (v.get("title") or "")[:80],
            "summary": (v.get("description") or "")[:300],
            "link": v.get("url") or f"https://www.youtube.com/watch?v={vid}",
            "heat": int(v.get("view_count") or 0),
            "published_at": v.get("published_time") or "",
            "author_raw": "",
            "dedup_key": f"对标账号:YouTube:{vid}",
        })
    return items


def fetch_wechat(username, since_hours=24*7):
    """微信公众号：tikhub.x.wechat-mp-v2-fetch-account-articles by username。"""
    if not username:
        return []
    resp = treg_call(
        "tikhub.x.wechat-mp-v2-fetch-account-articles",
        method="POST",
        data={"username": username, "page_size": 20, "raw": True},
    )
    if not resp:
        return []
    arts = (((resp.get("data") or {}).get("data") or {}).get("articles") or [])
    items = []
    for a in arts:
        url = a.get("url") or ""
        aid = a.get("aid") or url
        if not aid:
            continue
        ts = int(a.get("update_time") or a.get("create_time") or 0)
        if ts > 10**12:
            ts = ts / 1000
        dt = datetime.fromtimestamp(ts, tz=CST).strftime("%Y-%m-%dT%H:%M:%S+08:00") if ts else ""
        items.append({
            "platform": "微信公众号",
            "source_item_id": str(aid),
            "title": (a.get("title") or "")[:80],
            "summary": (a.get("digest") or a.get("content") or "")[:300],
            "link": url,
            "heat": int(a.get("read_count") or a.get("like_count") or 0),
            "published_at": dt,
            "author_raw": a.get("author") or "",
            "dedup_key": f"对标账号:微信公众号:{aid}",
        })
    return items


PLATFORM_FETCHERS = {
    "小红书": lambda plat: fetch_xiaohongshu(plat["id"]),
    "B站": lambda plat: fetch_bilibili(plat["id"]),
    "X": lambda plat: fetch_x(plat["id"]),
    "YouTube": lambda plat: fetch_youtube(plat["id"]),
    "微信公众号": lambda plat: fetch_wechat(plat["id"]),
}


# ---------- 主题推断 ----------
def infer_topics(account_name, title, summary, topic_map):
    """账号默认主题 + 标题/摘要关键词叠加。"""
    base = set(topic_map["account_topics"].get(account_name, ["AI 工具"]))
    text = (title or "") + " " + (summary or "")
    text_l = text.lower()
    for rule in topic_map["title_keyword_overrides"]:
        if any(kw.lower() in text_l for kw in rule["kw"]):
            base |= set(rule["add"])
    return sorted(base) if base else ["AI 工具"]


# ---------- 主流程 ----------
def fetch_all(since_hours=24*7):
    accounts = json.loads(ACCOUNTS_PATH.read_text())
    topic_map = json.loads(TOPIC_MAP_PATH.read_text())
    cutoff = datetime.now(CST) - timedelta(hours=since_hours)
    all_items = []
    stats = {}
    for acc in accounts:
        name = acc["name"]
        for platform_name, plat in acc["platforms"].items():
            stats_key = f"{name}/{platform_name}"
            fetcher = PLATFORM_FETCHERS.get(platform_name)
            if not fetcher:
                stats[stats_key] = ("skip", "no fetcher")
                continue
            try:
                items = fetcher(plat)
            except SkipPlatform as e:
                stats[stats_key] = ("skip", str(e))
                continue
            except Exception as e:
                stats[stats_key] = ("fail", str(e)[:80])
                continue
            new_items = []
            for it in items:
                if not it.get("published_at"):
                    new_items.append(it)
                    continue
                try:
                    ts = datetime.fromisoformat(it["published_at"]).astimezone(CST)
                    if ts < cutoff:
                        continue
                except Exception:
                    pass
                it["account"] = name
                it["topic"] = infer_topics(name, it.get("title", ""), it.get("summary", ""), topic_map)
                new_items.append(it)
            stats[stats_key] = ("ok", len(new_items))
            all_items += new_items
    return all_items, stats


def fetch_all_comments(posts):
    """抓取每个 post 的 top 评论。无关键词过滤，让下游 agent/创哥自己挑。

    返回 comment items，结构和 fetch_* 兼容。
    """
    all_comments = []
    comment_stats = {}
    for p in posts:
        plat = p.get("platform")
        sid = p.get("source_item_id")
        post_account = p.get("account") or "?"
        cf = COMMENT_FETCHERS.get(plat)
        if not cf:
            comment_stats[f"{post_account}/{plat}/{sid}"] = ("skip", "no comment fetcher")
            continue
        try:
            comments = cf(plat, sid)
        except Exception as e:
            comment_stats[f"{post_account}/{plat}/{sid}"] = ("fail", str(e)[:80])
            continue
        comment_stats[f"{post_account}/{plat}/{sid}"] = ("ok", len(comments))
        for c in comments:
            c["account"] = post_account
            c["post_title"] = p.get("title") or ""
            c["post_link"] = p.get("link") or ""
            c["topic"] = p.get("topic") or ["AI 工具"]
            c["published_at"] = p.get("published_at")  # 沿用原帖发布时间
            c["platform"] = plat
            # dedup_key 包含原帖 + 评论 ID，不与帖子 dedup 冲突
            c["dedup_key"] = f"对标账号评论:{plat}:{sid}:{c['comment_id']}"
        all_comments += comments
    return all_comments, comment_stats


def get_existing_dedup_map():
    """从飞书拉取 (Dedup Key, record_id) 映射表。返回 dict[key] = record_id。"""
    r = subprocess.run(
        ["lark-cli", "base", "+record-list",
         "--base-token", LARK_BASE_TOKEN,
         "--table-id", LARK_TABLE_ID,
         "--field-id", "Dedup Key",
         "--format", "ndjson",
         "--output", "/tmp/benchmark_existing_dedup.ndjson",
         "--overwrite"],
        capture_output=True, text=True,
    )
    mp = {}
    p = Path("/tmp/benchmark_existing_dedup.ndjson")
    if not p.exists():
        return mp
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
            rid = r.get("record_id")
            v = r.get("Dedup Key")
            if isinstance(v, list): v = v[0] if v else None
            if rid and v:
                mp[v] = rid
        except Exception:
            pass
    return mp


def filter_by_dedup(items):
    """过滤已经在飞书里的 Dedup Key。返回 (new_items, skipped_count, existing_map)。"""
    existing_map = get_existing_dedup_map()
    new_items = [it for it in items if it["dedup_key"] not in existing_map]
    return new_items, len(items) - len(new_items), existing_map


def build_records(items, since_hours=24*7):
    now = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    out = []
    for it in items:
        # 判断是帖子还是评论
        is_comment = "对标账号评论:" in it.get("dedup_key", "")
        if is_comment:
            post_title = it.get("post_title") or ""
            comment_text = (it.get("text") or "").strip()[:80]
            title = f"[评论] {post_title[:40]}：{comment_text}"
            summary = (it.get("text") or "")[:300]
            heat = it.get("likes") or 0
            author = it.get("user") or ""
            source_id = f"{it.get('source_item_id') or '?'}:{it.get('comment_id') or ''}"
            source_field = "对标账号评论"
            signal_field = "💬 问题"
        else:
            title = (it.get("title") or "(无标题)").strip()
            summary = it.get("summary") or ""
            heat = it.get("heat") or 0
            author = it.get("account") or ""
            source_id = it.get("source_item_id") or ""
            source_field = "对标账号"
            signal_field = SIGNAL_TYPE
        rec = {
            "标题": title,
            "摘要": summary,
            "链接": it.get("link"),
            "作者": author,
            "发布时间": it.get("published_at") or None,
            "抓取时间": now,
            "热度": heat,
            "来源": [source_field],
            "平台": [it["platform"]],
            "信号类型": [signal_field],
            "主题 Topic": it.get("topic") or ["AI 工具"],
            "行动状态": ["无"],
            "抓取状态": ["正常"],
            "Dedup Key": it["dedup_key"],
            "Source Item ID": source_id,
        }
        out.append({k: v for k, v in rec.items() if v is not None})
    return out


def format_comments_text(comments):
    """把一组评论格式化为多行文本。"""
    if not comments:
        return ""
    lines = []
    for c in comments:
        user = c.get("user") or "匿名"
        text = (c.get("text") or "").strip().replace("\n", " ")
        likes = c.get("likes") or 0
        if likes > 0:
            lines.append(f"[👍{likes}] {user}: {text}")
        else:
            lines.append(f"{user}: {text}")
    return "\n\n".join(lines)


def build_post_records_with_comments(posts, post_to_comments):
    """只写帖子记录。评论塞在「评论」字段里。不再写独立评论记录。"""
    now = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    out = []
    for it in posts:
        title = (it.get("title") or "(无标题)").strip()
        comments = post_to_comments.get(it["dedup_key"], [])
        comments_text = format_comments_text(comments)
        rec = {
            "标题": title,
            "摘要": it.get("summary") or "",
            "链接": it.get("link"),
            "作者": it.get("account") or "",
            "发布时间": it.get("published_at") or None,
            "抓取时间": now,
            "热度": it.get("heat") or 0,
            "来源": ["对标账号"],
            "平台": [it["platform"]],
            "信号类型": [SIGNAL_TYPE],
            "主题 Topic": it.get("topic") or ["AI 工具"],
            "行动状态": ["无"],
            "抓取状态": ["正常"],
            "Dedup Key": it["dedup_key"],
            "Source Item ID": it.get("source_item_id") or "",
            "评论": comments_text,
        }
        out.append({k: v for k, v in rec.items() if v is not None})
    return out
    now = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")
    out = []
    for it in items:
        # 判断是帖子还是评论
        is_comment = "对标账号评论:" in it.get("dedup_key", "")
        if is_comment:
            post_title = it.get("post_title") or ""
            comment_text = (it.get("text") or "").strip()[:80]
            title = f"[评论] {post_title[:40]}：{comment_text}"
            summary = (it.get("text") or "")[:300]
            heat = it.get("likes") or 0
            author = it.get("user") or ""
            source_id = f"{it.get('source_item_id') or '?'}:{it.get('comment_id') or ''}"
            source_field = "对标账号评论"
            signal_field = "💬 问题"
        else:
            title = (it.get("title") or "(无标题)").strip()
            summary = it.get("summary") or ""
            heat = it.get("heat") or 0
            author = it.get("account") or ""
            source_id = it.get("source_item_id") or ""
            source_field = "对标账号"
            signal_field = SIGNAL_TYPE
        rec = {
            "标题": title,
            "摘要": summary,
            "链接": it.get("link"),
            "作者": author,
            "发布时间": it.get("published_at") or None,
            "抓取时间": now,
            "热度": heat,
            "来源": [source_field],
            "平台": [it["platform"]],
            "信号类型": [signal_field],
            "主题 Topic": it.get("topic") or ["AI 工具"],
            "行动状态": ["无"],
            "抓取状态": ["正常"],
            "Dedup Key": it["dedup_key"],
            "Source Item ID": source_id,
        }
        out.append({k: v for k, v in rec.items() if v is not None})
    return out


def write_to_feishu(records, dry_run=False):
    if dry_run:
        print(f"[dry-run] would write {len(records)} records")
        return True
    path = Path("/tmp/benchmark_batch.json")
    payload = {"create_records": records}
    path.write_text(json.dumps(payload, ensure_ascii=False))
    for i in range(0, len(records), 200):
        chunk = records[i:i+200]
        chunk_payload = {"create_records": chunk}
        chunk_path = Path(f"/tmp/benchmark_batch_{i}.json")
        chunk_path.write_text(json.dumps(chunk_payload, ensure_ascii=False))
        r = subprocess.run(
            ["lark-cli", "base", "+record-batch-create",
             "--base-token", LARK_BASE_TOKEN,
             "--table-id", LARK_TABLE_ID,
             "--json", f"@{chunk_path}"],
            capture_output=True, text=True,
        )
        try:
            j = json.loads(r.stdout)
            if j.get("ok"):
                print(f"  +{len(chunk)} records ok")
            else:
                print(f"  FAIL chunk {i}: {j.get('error')}")
                return False
        except Exception:
            print(f"  FAIL parse: {r.stdout[:200]}")
            return False
    return True


def update_existing_comments(posts, post_to_comments, existing_map):
    """更新已存在帖子的「评论」字段。用 +record-batch-update（200/call）。"""
    if not existing_map:
        return 0
    update_map = {}
    for it in posts:
        rid = existing_map.get(it["dedup_key"])
        if not rid:
            continue
        comments = post_to_comments.get(it["dedup_key"], [])
        comments_text = format_comments_text(comments)
        update_map[rid] = {
            "评论": comments_text,
            "抓取时间": datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        }
    if not update_map:
        return 0
    ok_total = 0
    items = list(update_map.items())
    for i in range(0, len(items), 200):
        chunk = dict(items[i:i+200])
        payload = {"update_records": chunk}
        path = Path(f"/tmp/benchmark_update_batch_{i}.json")
        path.write_text(json.dumps(payload, ensure_ascii=False))
        r = subprocess.run(
            ["lark-cli", "base", "+record-batch-update",
             "--base-token", LARK_BASE_TOKEN,
             "--table-id", LARK_TABLE_ID,
             "--json", f"@{path}"],
            capture_output=True, text=True,
        )
        try:
            j = json.loads(r.stdout)
            if j.get("ok"):
                ok_total += len(chunk)
                print(f"  ~{len(chunk)} records updated")
            else:
                print(f"  UPDATE FAIL chunk {i}: {j.get('error')}")
        except Exception:
            print(f"  UPDATE PARSE FAIL: {r.stdout[:200]}")
    return ok_total


def compute_since_hours(args, since):
    """智能 since-hours：不传则默认 24h，但 cron 漏跑后自动回溯。"""
    if since is not None:
        return since, "explicit"
    last_run_path = LAST_RUN_PATH
    if not last_run_path.exists():
        return DEFAULT_SINCE_HOURS, "first-run"
    try:
        last = json.loads(last_run_path.read_text()).get("last_run")
        if not last:
            return DEFAULT_SINCE_HOURS, "no-timestamp"
        last_dt = datetime.fromisoformat(last).astimezone(CST)
        gap_hours = (datetime.now(CST) - last_dt).total_seconds() / 3600
        # cron 正常则约 24h；如果超过 24h，漏跑了，补上中间
        since = min(int(gap_hours) + BACKFILL_BUFFER_HOURS, MAX_BACKFILL_HOURS)
        return max(since, DEFAULT_SINCE_HOURS), f"backfill-from-{last[:10]}-gap={gap_hours:.1f}h"
    except Exception as e:
        return DEFAULT_SINCE_HOURS, f"parse-fail:{e}"


def save_last_run():
    """记录本次完成时间，供下次智能回溯。"""
    LAST_RUN_PATH.write_text(json.dumps({"last_run": datetime.now(CST).isoformat()}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since-hours", type=int, default=None,
                    help="拉多久内的新作品。不传则智能默认：24h 或上次跑后的回溯窗口")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    since_hours, reason = compute_since_hours(args, args.since_hours)
    print(f"[benchmark-pull] start since={since_hours}h reason={reason} dry_run={args.dry_run}")
    args.since_hours = since_hours  # 后面 fetch_all / build_records 用到
    items, stats = fetch_all(args.since_hours)
    for k, v in stats.items():
        print(f"  {k}: {v[0]} ({v[1]})")
    print(f"[benchmark-pull] fetched {len(items)} items")

    if not items:
        print("[benchmark-pull] no items; exit")
        return

    # 中间产物
    state_path = STATE_DIR / "benchmark_posts.ndjson"
    with state_path.open("w") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"[benchmark-pull] state: {state_path}")

    # 抓评论（不过滤，all-in）。评论以帖子身份保存到信息流帖子的「评论」字段。
    comments, comment_stats = fetch_all_comments(items)
    if comment_stats:
        print(f"[benchmark-pull] comments:")
        for k, v in comment_stats.items():
            print(f"  {k}: {v[0]} ({v[1]})")
        print(f"[benchmark-pull] fetched {len(comments)} comments")
    # 评论中间产物
    comments_state = STATE_DIR / "benchmark_comments.ndjson"
    with comments_state.open("w") as f:
        for it in comments:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

    # 把评论绑定到对应帖子上（去重只针对帖子）
    post_to_comments = {}
    for c in comments:
        # 评论的 link 里含原帖的 source_item_id
        # 靠 dedup_key 反推帖子 key
        m = c["dedup_key"].split(":")
        if len(m) >= 4:
            post_key = f"对标账号:{m[1]}:{m[2]}"  # 对标账号:<平台>:<原帖ID>
        else:
            continue
        post_to_comments.setdefault(post_key, []).append(c)

    # dedup：区分新帖 vs 已存在帖
    new_posts, skipped, existing_map = filter_by_dedup(items)
    print(f"[benchmark-pull] dedup: new={len(new_posts)} skipped(existing)={skipped}")

    if not items:
        print("[benchmark-pull] nothing; exit")
        save_last_run()
        return

    if args.dry_run:
        print(f"[dry-run] sample new record:")
        if new_posts:
            sample = build_post_records_with_comments(new_posts[:1], post_to_comments)[0]
            print(json.dumps(sample, ensure_ascii=False, indent=2))
        print(f"[dry-run] sample update record:")
        if skipped:
            for it in items:
                if it["dedup_key"] in existing_map:
                    sample = build_post_records_with_comments([it], post_to_comments)[0]
                    print(json.dumps(sample, ensure_ascii=False, indent=2))
                    break
        return

    # 新帖：create
    ok_create = True
    if new_posts:
        records_new = build_post_records_with_comments(new_posts, post_to_comments)
        ok_create = write_to_feishu(records_new, dry_run=False)
        print(f"  +{len(new_posts)} new posts")
    else:
        print(f"  0 new posts")

    # 旧帖：update（带最新评论）
    n_updated = update_existing_comments(items, post_to_comments, existing_map)

    print(f"[benchmark-pull] write_to_feishu: create {'ok' if ok_create else 'fail'} | update={n_updated}")
    if ok_create or n_updated:
        save_last_run()
        print(f"[benchmark-pull] saved last_run -> {LAST_RUN_PATH}")
        write_im_report(items, new_posts, stats, since_hours, reason, post_to_comments)


def write_im_report(all_items, kept, stats, since_hours, reason, post_to_comments=None):
    """生成 IM 报告文本，给 multica agent 发飞书 IM。"""
    n_posts = len(kept)
    n_comments = sum(len(v) for v in (post_to_comments or {}).values())
    by_account = {}
    for it in kept:
        a = it.get("account") or "?"
        by_account[a] = by_account.get(a, 0) + 1
    quiet = sorted([k.split("/")[0] for k, v in stats.items() if v[0] == "ok" and v[1] == 0 and "/" in k])
    skipped = sorted([k for k, v in stats.items() if v[0] == "skip"])
    failed = sorted([k for k, v in stats.items() if v[0] == "fail"])

    lines = [f"✅ benchmark-pull · {datetime.now(CST).strftime('%Y-%m-%d %H:%M')}"]
    lines.append(f"since {since_hours}h（{reason}）· 新写 {n_posts} 帖子 + {n_comments} 评论（嵌入帖子）")
    if by_account:
        per = " / ".join(f"{a} +{n}" for a, n in sorted(by_account.items(), key=lambda x: -x[1]))
        lines.append(f"各账号新增：{per}")
    if quiet:
        lines.append(f"无动的账号：{', '.join(quiet)}（正常）")
    if skipped:
        lines.append(f"skip：{', '.join(skipped)}")
    if failed:
        lines.append(f"⚠️ fail：{', '.join(failed)}")
    text = "\n".join(lines)
    (STATE_DIR / "im_report.txt").write_text(text, encoding="utf-8")
    print(f"[benchmark-pull] im report -> {STATE_DIR / 'im_report.txt'}")
    print("---")
    print(text)
    print("---")


if __name__ == "__main__":
    main()