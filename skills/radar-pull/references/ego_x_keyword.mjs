// X 关键词全量搜索（ego-browser 兜底版）
// 用法: ego-browser nodejs < references/ego_x_keyword.mjs
// 输出: stdout JSON 数组（agent 自己 parse + 写飞书）
// 备注: 当 treg balance 耗尽时用这个；user 必须已在 ego-browser 登录 X
const fs = require('fs');
const path = require('path');
// ego-browser context: process.cwd() = "/", __dirname undefined.
// Use SKILL_DIR env var (set by agent) or fall back to absolute default.
const SKILL_DIR = process.env.SKILL_DIR || '/Users/junjie/work/topic-radar/skills/radar-pull';
const KEYWORDS_FILE = path.join(SKILL_DIR, 'references', 'keywords_x.txt');
const OUTPUT = path.join(SKILL_DIR, 'state', 'ego_x_search.ndjson');

const KEYWORDS = fs.readFileSync(KEYWORDS_FILE, 'utf8').trim().split('\n').filter(Boolean);
const PER_KEYWORD = 10;

async function searchOne(query) {
  const url = 'https://x.com/search?q=' + encodeURIComponent(query) + '&src=typed_query&f=top';
  try {
    await openOrReuseTab(url, { wait: true, timeout: 45 });
    await wait(4);
    // 滚动 2 屏，拿更多结果
    for (let s = 0; s < 2; s++) {
      await js(String.raw`window.scrollBy(0, window.innerHeight)`);
      await wait(2);
    }
    return await js(`(() => {
      const articles = [...document.querySelectorAll('article')];
      return articles.slice(0, ${PER_KEYWORD}).map(a => {
        const text = (a.innerText || '').split('\\n').filter(l => l.trim()).join(' ').slice(0, 280);
        const link = a.querySelector('a[href*="/status/"]');
        const href = link ? link.getAttribute('href') : '';
        const m = (href || '').match(/\\/status\\/(\\d+)/);
        const id = m ? m[1] : '';
        const lines = (a.innerText || '').split('\\n').filter(l => l.trim());
        const author = lines.find(l => /^@/.test(l.trim())) || '';
        // 互动数（aria-label）
        const eng = { replies: 0, reposts: 0, likes: 0, views: 0 };
        [...a.querySelectorAll('[aria-label]')].forEach(e => {
          const lbl = e.getAttribute('aria-label') || '';
          const m2 = lbl.match(/([\\d.,KMB]+)\\s*(Replies|Reposts|Likes|Views)/i);
          if (m2) {
            let v = parseFloat(m2[1].replace(/,/g, ''));
            if (/K$/i.test(m2[1])) v *= 1000;
            if (/M$/i.test(m2[1])) v *= 1000000;
            eng[m2[2].toLowerCase()] = Math.round(v);
          }
        });
        return {
          id, author: author.replace(/^@/, ''),
          text, href: href.startsWith('/') ? 'https://x.com' + href : href,
          heat: eng.views || eng.likes || 0,
        };
      }).filter(t => t.id);
    })()`);
  } catch (e) {
    cliLog('[' + query + '] ERROR ' + e.message);
    return [];
  }
}

async function main() {
  const task = await useOrCreateTaskSpace('X keyword search (ego)');
  const allPosts = [];
  for (const kw of KEYWORDS) {
    cliLog('[' + kw + '] searching...');
    const posts = await searchOne(kw);
    posts.forEach(p => p.keyword = kw);
    allPosts.push(...posts);
    cliLog('[' + kw + '] got ' + posts.length + ' tweets');
    await wait(2);
  }
  // 写到 state/ego_x_search.ndjson
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, allPosts.map(p => JSON.stringify(p)).join('\n'));
  cliLog('TOTAL ' + allPosts.length + ' tweets written to ' + OUTPUT);
  console.log(JSON.stringify(allPosts, null, 2));
}
main().catch(e => cliLog('FATAL ' + e.message));