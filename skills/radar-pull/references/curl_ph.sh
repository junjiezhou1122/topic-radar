#!/bin/bash
# Product Hunt RSS 全量拉取
# 用法: bash references/curl_ph.sh
set -e
curl -sL --max-time 30 https://www.producthunt.com/feed | python3 -c "
import sys, re, html
ns = {'a': 'http://www.w3.org/2005/Atom'}
import xml.etree.ElementTree as ET
root = ET.fromstring(sys.stdin.read())
out = []
for e in root.findall('a:entry', ns):
    link_el = e.find('a:link', ns)
    eid = e.findtext('a:id', default='', namespaces=ns) or ''
    m = re.search(r'Post/(\d+)', eid)
    content_html = e.findtext('a:content', default='', namespaces=ns) or ''
    summary = re.sub(r'<[^>]+>', '', content_html).strip()
    title = (e.findtext('a:title', default='', namespaces=ns) or '').strip()
    out.append({
        'id': eid,
        'title': title,
        'link': link_el.get('href', '') if link_el is not None else '',
        'author': (e.findtext('a:author/a:name', default='', namespaces=ns) or '').strip(),
        'heat': 0,
        'source': 'Product Hunt',
        'platform': 'Product Hunt',
        'signal_type': '🛠 方案',
        'source_item_id': m.group(1) if m else eid,
        'published_at': e.findtext('a:updated', default='', namespaces=ns) or '',
        'summary': summary[:300],
    })
import json; print(json.dumps(out, ensure_ascii=False))
"
