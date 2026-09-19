// 小红书 AI 关键词全量搜索（ego-browser 兜底版）
// 用法: ego-browser nodejs < references/ego_xhs_keyword.mjs
// 输出: stdout JSON 数组
// 备注: treg 耗尽时用这个；user 必须已在 ego-browser 登录小红书
const fs = require('fs');
const path = require('path');
const SKILL_DIR = process.env.SKILL_DIR || '/Users/junjie/work/topic-radar/skills/radar-pull';
const KEYWORDS_FILE = path.join(SKILL_DIR, 'references', 'keywords_xhs.txt');
const OUTPUT = path.join(SKILL_DIR, 'state', 'ego_xhs_search.ndjson');

const KEYWORDS = fs.readFileSync(KEYWORDS_FILE, 'utf8').trim().split('\n').filter(Boolean);
const PER_KEYWORD = 10;

async function searchOne(query) {
  const url = 'https://www.xiaohongshu.com/search_result?keyword=' + encodeURIComponent(query) + '&source=web_search_result_notes';
  try {
    await openOrReuseTab(url, { wait: true, timeout: 60 });
    await wait(6);
    return await js(`(() => {
      // 尝试多个选择器，兼容小红包改版
      const cards = [...document.querySelectorAll('.feeds-page .note-item, section.note-item, .note-item')];
      let result = cards.slice(0, ${PER_KEYWORD}).map(c => {
        const title = c.querySelector('.title span, .footer .title, .title')?.innerText || '';
        const author = c.querySelector('.author .name, .nickname')?.innerText || '';
        const linkEl = c.tagName === 'A' ? c : c.querySelector('a');
        const href = (linkEl ? linkEl.getAttribute('href') : '') || '';
        const noteIdMatch = href.match(/search_result\\/([a-z0-9]+)/i) || href.match(/explore\\/([a-z0-9]+)/i);
        const noteId = noteIdMatch ? noteIdMatch[1] : '';
        return {
          noteId, title: title.trim().slice(0, 200),
          author: author.trim().slice(0, 50),
          href: href.startsWith('http') ? href : ('https://www.xiaohongshu.com' + (href.startsWith('/') ? href : '/' + href)),
        };
      });
      // 兜底：直接抓所有 note 链接
      if (result.length === 0) {
        result = [...document.querySelectorAll('a')]
          .filter(a => /search_result|explore/.test(a.href))
          .slice(0, ${PER_KEYWORD})
          .map(a => {
            const noteIdMatch = a.href.match(/search_result\\/([a-z0-9]+)/i) || a.href.match(/explore\\/([a-z0-9]+)/i);
            return {
              noteId: noteIdMatch ? noteIdMatch[1] : '',
              title: (a.innerText || '').trim().slice(0, 200),
              author: '', href: a.href,
            };
          });
      }
      return result.filter(n => n.noteId);
    })()`);
  } catch (e) {
    cliLog('[' + query + '] ERROR ' + e.message);
    return [];
  }
}

async function main() {
  const task = await useOrCreateTaskSpace('XHS keyword search (ego)');
  const all = [];
  for (const kw of KEYWORDS) {
    cliLog('[' + kw + '] searching...');
    const notes = await searchOne(kw);
    notes.forEach(n => n.keyword = kw);
    all.push(...notes);
    cliLog('[' + kw + '] got ' + notes.length + ' notes');
    await wait(2);
  }
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  fs.writeFileSync(OUTPUT, all.map(n => JSON.stringify(n)).join('\n'));
  cliLog('TOTAL ' + all.length + ' notes written to ' + OUTPUT);
  console.log(JSON.stringify(all, null, 2));
}
main().catch(e => cliLog('FATAL ' + e.message));