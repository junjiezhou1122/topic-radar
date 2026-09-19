// X AI 圈列表读取脚本（边滚边抓）
// 用法: ego-browser nodejs < xlist_read.mjs
// 输出: $SKILL_DIR/state/xlist_posts.ndjson（每条 post 一行 JSON）
const fs = require('fs');
const path = require('path');
const SKILL_DIR = process.env.SKILL_DIR || '/Users/junjie/work/topic-radar/skills/radar-pull';
const STATE_DIR = path.join(SKILL_DIR, 'state');

const LISTS = ['AI', 'AI Leaders', 'AI High Signal', 'Researcher'];
const SCREENS = 3; // 每个 list 滚动几屏（含首屏共 SCREENS+1 次抓取）

const extractArticles = async () => js(String.raw`(() => {
  const arts = [...document.querySelectorAll('article')];
  return arts.map(a => {
    const text = a.innerText || '';
    const lines = text.split('\n').filter(l => l.trim());
    const authorLine = lines.find(l => /^@/.test(l.trim())) || '';
    const body = lines.filter(l =>
      !/^@/.test(l.trim()) &&
      !/^\d+(s|m|h|d|\s)/.test(l.trim()) &&
      !/Reposted/.test(l) &&
      !/^\d+$/.test(l.trim())
    ).join(' ').slice(0, 400);
    const link = a.querySelector('a[href*="/status/"]');
    const href = link ? link.getAttribute('href') : '';
    const full = href.startsWith('/') ? 'https://x.com' + href : href;
    const m = (href || '').match(/\/status\/(\d+)/);
    // 互动数（aria-label 里带数字）
    const eng = { replies: 0, reposts: 0, likes: 0, views: 0 };
    const labels = [...a.querySelectorAll('[aria-label]')].map(e => e.getAttribute('aria-label'));
    const num = (s) => { const mm = s && s.match(/([\d.,KMB]+)\s*(Replies|Reposts|Likes|Views)/i); if (!mm) return 0; const v = mm[1].replace(/,/g, ''); if (/K$/i.test(v)) return Math.round(parseFloat(v) * 1000); if (/M$/i.test(v)) return Math.round(parseFloat(v) * 1000000); return parseFloat(v) || 0; };
    for (const l of labels) {
      if (/Replies/i.test(l)) eng.replies = num(l);
      if (/Reposts/i.test(l)) eng.reposts = num(l);
      if (/Likes/i.test(l)) eng.likes = num(l);
      if (/Views/i.test(l)) eng.views = num(l);
    }
    return { author: authorLine.replace('·', '').trim(), body, link: full, tweet_id: m ? m[1] : '', list: null, views: eng.views, likes: eng.likes, reposts: eng.reposts, replies: eng.replies };
  });
})()`);

async function main() {
  const task = await useOrCreateTaskSpace('X list radar');
  await openOrReuseTab('https://x.com/home', { wait: true, timeout: 45 });
  await wait(4);

  const posts = [];
  const seen = new Set();

  for (const listName of LISTS) {
    const listJson = JSON.stringify(listName);
    const clicked = await js(String.raw`(() => {
      const all = [...document.querySelectorAll('*')];
      const el = all.find(e => e.children.length === 0 && (e.innerText || '').trim() === ${listJson});
      if (!el) return false;
      const tab = el.closest('[role="tab"]') || el;
      tab.click();
      return true;
    })()`);
    if (!clicked) {
      cliLog('skip: tab not found for ' + listName);
      continue;
    }
    await wait(3);

    // 边滚边抓：虚拟列表会回收离屏元素，每屏滚动后抓一次再继续
    const vh = (await pageInfo()).ph || 900;
    for (let s = 0; s <= SCREENS; s++) {
      if (s > 0) {
        await scrollBy(vh);
        await wait(2);
      }
      const items = await extractArticles();
      for (const it of items) {
        if (!it.body || !it.link) continue;
        if (seen.has(it.link)) continue;
        seen.add(it.link);
        it.list = listName;
        posts.push(it);
      }
      cliLog('[' + listName + '] screen ' + s + ': ' + posts.length + ' unique total');
    }
    await js(String.raw`window.scrollTo(0, 0)`);
    await wait(1);
  }

  fs.mkdirSync(STATE_DIR, { recursive: true });
  const out = posts.slice(0, 200).map(p => JSON.stringify(p));
  fs.writeFileSync(STATE_DIR + '/xlist_posts.ndjson', out.join('\n'));
  cliLog('WROTE ' + posts.length + ' unique posts to ' + STATE_DIR + '/xlist_posts.ndjson');
}

main().catch(e => cliLog('ERROR: ' + e.message));
