# -*- coding: utf-8 -*-
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import ta_news_window as w  # noqa: E402

_failed = []


def eq(a, b, msg):
    if a != b:
        _failed.append(msg)
        print(f'  [FAIL] {msg}\n      기대: {b!r}\n      실제: {a!r}')


XML = '''<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<item><title>HD현대중공업, EB 오버행 부담에 6%대 급락 - 뉴스1</title><link>https://x/1</link><pubDate>Wed, 01 Apr 2026 06:30:00 GMT</pubDate></item>
<item><title>배당 결정</title><link>https://x/2</link><pubDate>Tue, 31 Mar 2026 09:00:00 GMT</pubDate><source url="https://c">조선비즈</source></item>
</channel></rss>'''
rows = w.parse_rss(XML)
eq(len(rows), 2, 'item 2개')
eq(rows[0]['title'], 'HD현대중공업, EB 오버행 부담에 6%대 급락', '제목 끝 매체명 분리')
eq(rows[0]['source'], '뉴스1', 'source = 매체')
eq(rows[1]['source'], '조선비즈', 'source 태그 우선')
eq(rows[0]['datetime'][:10], '2026-04-01', 'pubDate -> ISO 날짜')
eq(w.window_query('HD현대중공업', '2026-04-01'), 'HD현대중공업 after:2026-03-30 before:2026-04-03', '창: d-2 ~ d+1 (before 는 배타라 +2)')
got = w.fetch_window('HD현대중공업', '2026-04-01', fetch=lambda q: XML)
eq([r['title'] for r in got], ['HD현대중공업, EB 오버행 부담에 6%대 급락', '배당 결정'], 'fetch_window 는 주입한 fetch 를 쓴다')

print('=' * 66)
if _failed:
    print(f'  ta_news_window 테스트: {len(_failed)}개 실패')
    sys.exit(1)
print('  ta_news_window 테스트: 7개 통과 / 0개 실패')
