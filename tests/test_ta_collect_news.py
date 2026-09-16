"""ta_collect_news 테스트 (Task 2).

네트워크 없이 fetch 주입으로 돈다. 실행: python tests/test_ta_collect_news.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import datetime as dt                                     # noqa: E402
import ta_collect_news as tn                               # noqa: E402
import ta_common as tc                                     # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


# ---------- fetch 대역 ----------
class _Resp:
    def __init__(self, status=200, payload=None, raise_exc=None):
        self.status_code = status
        self._payload = payload
        self._raise = raise_exc

    def json(self):
        if self._raise:
            raise self._raise
        return self._payload


def _fetch_seq(responses):
    """호출할 때마다 순서대로 반환. 예외 객체를 넣으면 그 예외를 올린다."""
    it = iter(responses)

    def fetch(url, params=None, headers=None):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    return fetch


# ==================== 1. 네이버 종목뉴스 파서 ====================
CUTOFF = dt.datetime(2026, 9, 1, 0, 0, tzinfo=tc.KST)

STOCK_GROUP_PAGE1 = [{
    "total": 2,
    "items": [
        {"id": "1", "officeId": "011", "articleId": "100001", "officeName": "서울경제",
         "datetime": "202609151030", "type": "news",
         "title": "에프에스티, 3분기 &quot;실적&quot; 개선 기대", "body": "본문 &amp; 내용",
         "titleFull": "에프에스티, 3분기 &quot;실적&quot; 개선 기대",
         "mobileNewsUrl": "https://n.news.naver.com/mnews/article/011/0100001"},
        {"id": "2", "officeId": "015", "articleId": "100002", "officeName": "한국경제",
         "datetime": "202609140900", "type": "news",
         "title": "에프에스티 특징주 급등", "body": "장중 강세",
         "titleFull": "에프에스티 특징주 급등", "mobileNewsUrl": None},
    ],
}]
STOCK_GROUP_PAGE2_OLD = [{
    "total": 1,
    "items": [
        {"id": "3", "officeId": "020", "articleId": "100003", "officeName": "매일경제",
         "datetime": "202608010900", "type": "news",
         "title": "오래된 뉴스", "body": "cutoff 이전", "titleFull": "오래된 뉴스",
         "mobileNewsUrl": "https://n.news.naver.com/mnews/article/020/0100003"},
    ],
}]

r1 = tn.collect_naver_stock('036810', CUTOFF, max_pages=2,
                            fetch=_fetch_seq([_Resp(payload=STOCK_GROUP_PAGE1),
                                              _Resp(payload=STOCK_GROUP_PAGE2_OLD)]),
                            delay=0)
eq(r1['status'], 'ok', '정상 응답은 status ok')
eq(len(r1['items']), 2, '경계 페이지(2페이지)의 cutoff 이전 아이템은 담지 않는다 (fix round 3)')
eq(r1.get('truncated'), None, 'cutoff 로 멈췄으면 truncated 는 없다')
eq(r1['items'][0]['title'], '에프에스티, 3분기 "실적" 개선 기대', 'titleFull 엔티티 unescape')
eq(r1['items'][0]['body'], '본문 & 내용', 'body 도 unescape')
eq(r1['items'][0]['url'], 'https://n.news.naver.com/mnews/article/011/0100001',
   'mobileNewsUrl 그대로 사용')
eq(r1['items'][1]['url'], 'https://n.news.naver.com/mnews/article/015/100002',
   'mobileNewsUrl 없으면 officeId/articleId 로 조립')
eq(r1['items'][0]['datetime'], dt.datetime(2026, 9, 15, 10, 30, tzinfo=tc.KST),
   'datetime 파싱 (KST)')
eq(r1['pages'], 2, 'cutoff 이전 페이지까지 읽고 중단 (2페이지)')

# 빈 리스트를 만나면 즉시 중단
r2 = tn.collect_naver_stock('036810', CUTOFF, max_pages=5,
                            fetch=_fetch_seq([_Resp(payload=STOCK_GROUP_PAGE1), _Resp(payload=[])]),
                            delay=0)
eq(r2['pages'], 2, '빈 응답에서 멈춘다')
eq(len(r2['items']), 2, '빈 페이지 이전 items 만 남는다')
eq(r2.get('truncated'), None, '빈 페이지로 끝났으면(정상 종료) truncated 아니다')

# max_pages 도달 -- cutoff 도 빈 페이지도 못 보고 끊겼으면 truncated
r3 = tn.collect_naver_stock('036810', CUTOFF, max_pages=1,
                            fetch=_fetch_seq([_Resp(payload=STOCK_GROUP_PAGE1)]), delay=0)
eq(r3['pages'], 1, 'max_pages 도달하면 멈춘다')
eq(r3['truncated'], True, 'max_pages 로 끊기면 truncated=True (fix round 3)')
eq('max_pages' in r3['truncated_reason'], True, 'truncated_reason 에 원인 명시')


# ---------- 경계 페이지 혼합(cutoff 전후 섞인 페이지) ----------
STOCK_GROUP_MIXED = [{
    "total": 3,
    "items": [
        {"id": "1", "officeId": "011", "articleId": "1", "officeName": "A",
         "datetime": "202609020900", "titleFull": "cutoff 이후 1", "body": "x",
         "mobileNewsUrl": "http://n/1"},
        {"id": "2", "officeId": "011", "articleId": "2", "officeName": "A",
         "datetime": "202608310900", "titleFull": "cutoff 이전 1", "body": "x",
         "mobileNewsUrl": "http://n/2"},
        {"id": "3", "officeId": "011", "articleId": "3", "officeName": "A",
         "datetime": "202608290900", "titleFull": "cutoff 이전 2", "body": "x",
         "mobileNewsUrl": "http://n/3"},
    ],
}]
r1b = tn.collect_naver_stock('036810', CUTOFF, max_pages=3,
                             fetch=_fetch_seq([_Resp(payload=STOCK_GROUP_MIXED)]), delay=0)
eq(len(r1b['items']), 1, '한 페이지 안에서도 cutoff 이후 아이템만 남는다 (경계 페이지 오염 차단)')
eq(r1b['items'][0]['title'], 'cutoff 이후 1', 'cutoff 이후 아이템만 유지')
eq(r1b['pages'], 1, '그 페이지의 최솟값이 cutoff 이전이므로 다음 페이지는 안 본다')


# ==================== 2. 네이버 검색 API 파서 ====================
SEARCH_PAGE1 = {"items": [
    {"title": "에프에스티 <b>실적</b> 서프라이즈", "originallink": "http://a.com/1",
     "link": "https://news.naver.com/1", "description": "<b>펠리클</b> 확장 투자",
     "pubDate": "Tue, 15 Sep 2026 10:30:00 +0900"},
    {"title": "오래된 검색결과", "originallink": "http://a.com/2",
     "link": "https://news.naver.com/2", "description": "cutoff 이전",
     "pubDate": "Fri, 01 Aug 2026 09:00:00 +0900"},
]}
os.environ['NAVER_CLIENT_ID'] = 'dummy'
os.environ['NAVER_CLIENT_SECRET'] = 'dummy'
r4 = tn.collect_naver_search('에프에스티', CUTOFF,
                             fetch=_fetch_seq([_Resp(payload=SEARCH_PAGE1)]), delay=0)
eq(r4['status'], 'ok', '검색 API 정상 응답')
eq(len(r4['items']), 1, 'cutoff 이전 항목은 제외')
eq(r4['items'][0]['title'], '에프에스티 실적 서프라이즈', '<b> 태그 제거')
eq(r4['items'][0]['body'], '펠리클 확장 투자', 'description 도 태그 제거')
eq(r4['items'][0]['datetime'], dt.datetime(2026, 9, 15, 10, 30, tzinfo=tc.KST),
   'pubDate -> KST ISO 동일 시각')
eq(r4.get('truncated'), None, 'cutoff 로 멈췄으면 truncated 아니다')

_id, _secret = os.environ.pop('NAVER_CLIENT_ID'), os.environ.pop('NAVER_CLIENT_SECRET')
r4b = tn.collect_naver_search('에프에스티', CUTOFF, fetch=_fetch_seq([]), delay=0)
eq(r4b['status'], 'failed', '키 없으면 failed (fetch 호출 전에 걸러진다)')
os.environ['NAVER_CLIENT_ID'], os.environ['NAVER_CLIENT_SECRET'] = _id, _secret

# start 가 max_start(1000) 에 도달할 때까지 cutoff 를 못 만나면 truncated
_NEVER_OLD_PAGE = {"items": [
    {"title": "최신 기사", "originallink": "http://a.com/x", "link": "http://a.com/x",
     "description": "d", "pubDate": "Tue, 15 Sep 2026 10:30:00 +0900"},
]}
r4c = tn.collect_naver_search('에프에스티', CUTOFF,
                              fetch=_fetch_seq([_Resp(payload=_NEVER_OLD_PAGE)] * 10), delay=0)
eq(r4c['pages'], 10, 'start=1,101,...,901 총 10회 조회 후 max_start 초과로 종료')
eq(r4c['truncated'], True, 'cutoff 를 못 만나고 max_start 로 끝나면 truncated=True (fix round 3)')
eq('start' in r4c['truncated_reason'], True, 'truncated_reason 에 원인 명시')


# ==================== 3. 관련성 / reaction 분류 + 중복 제거 ====================
items_mix = [
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 15, 10, 0, tzinfo=tc.KST),
     'office': 'A', 'title': '에프에스티, 실적 개선', 'body': 'x', 'url': 'http://u/1'},
    {'source': 'naver_search', 'datetime': dt.datetime(2026, 9, 15, 9, 0, tzinfo=tc.KST),
     'office': '', 'title': '에프에스티, 실적 개선', 'body': 'y', 'url': 'http://u/2'},
    {'source': 'naver_search', 'datetime': dt.datetime(2026, 9, 14, 9, 0, tzinfo=tc.KST),
     'office': '', 'title': '에프에스티 특징주 급등', 'body': 'z', 'url': 'http://u/3'},
    {'source': 'naver_search', 'datetime': dt.datetime(2026, 9, 13, 9, 0, tzinfo=tc.KST),
     'office': '', 'title': '삼성전자 신제품 발표', 'body': 'w', 'url': 'http://u/4'},
]
deduped = tn._dedupe(items_mix)
eq(len(deduped), 3, '같은 제목(공백/기호 무시) 다른 출처는 하나만 남는다')
eq(deduped[0]['source'], 'naver_stock', '중복이면 naver_stock 이 우선(먼저 온 것 유지)')

# url 도 제목도 없는 아이템: (datetime, office) 로 대체 dedupe (fix round 3)
empty_key_items = [
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 15, 10, 0, tzinfo=tc.KST),
     'office': 'A', 'title': '', 'body': 'p', 'url': ''},
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 15, 10, 0, tzinfo=tc.KST),
     'office': 'A', 'title': '', 'body': 'p-dup', 'url': ''},  # 같은 (datetime, office) -> 중복
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 14, 9, 0, tzinfo=tc.KST),
     'office': 'A', 'title': '', 'body': 'q', 'url': ''},      # datetime 다름 -> 별개 기사
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 15, 10, 0, tzinfo=tc.KST),
     'office': 'B', 'title': '', 'body': 'r', 'url': ''},      # office 다름 -> 별개 기사
]
deduped2 = tn._dedupe(empty_key_items)
eq(len(deduped2), 3, 'url·제목 둘 다 비어도 무한통과하지 않고 (datetime, office) 로 걸러진다')
eq(deduped2[0]['body'], 'p', '같은 (datetime, office) 중 먼저 온 것만 남는다')

finalized = tn._finalize(deduped, '에프에스티')
eq(finalized[0]['nid'], 'N0001', 'nid 는 N0001 부터')
eq([f['datetime'] for f in finalized], sorted([f['datetime'] for f in finalized], reverse=True),
   'datetime 내림차순 정렬')
by_title = {f['title']: f for f in finalized}
eq(by_title['에프에스티, 실적 개선']['relevant'], True, '종목명이 제목에 있으면 relevant')
eq(by_title['에프에스티, 실적 개선']['type'], 'news', '일반 기사는 type news')
eq(by_title['에프에스티 특징주 급등']['type'], 'reaction', '특징주 제목은 reaction')
eq(by_title['삼성전자 신제품 발표']['relevant'], False, '종목명 없으면 relevant false')


# ==================== 3b. mention/list_mention (controller fix round 1) ====================
# 실측 사고: naver_search 본문의 '관련주 나열' / '동반언급'이 relevant 를 오염시켰다.
_MENTION_ITEMS = [
    # (a) 제목 언급 -> relevant (출처 무관)
    {'source': 'naver_search', 'datetime': dt.datetime(2026, 9, 15, 12, 0, tzinfo=tc.KST),
     'office': '', 'title': '에프에스티, 3분기 실적 개선 전망',
     'body': '펠리클 확장 투자 재원 확보 목적', 'url': 'http://u/a'},
    # (b) naver_stock 본문 단독 언급, 나열형 아님 -> relevant
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 15, 11, 0, tzinfo=tc.KST),
     'office': 'X', 'title': '반도체 소부장 강세',
     'body': '에프에스티가 3분기 실적 개선 기대감에 강세를 보이고 있다.', 'url': 'http://u/b'},
    # (c) 나열형 언급(콤마 4개+) -> not relevant, list_mention True (naver_stock이어도 나열이면 제외)
    {'source': 'naver_stock', 'datetime': dt.datetime(2026, 9, 15, 10, 0, tzinfo=tc.KST),
     'office': 'Y', 'title': '반도체 장비 테마 강세',
     'body': '반도체 장비 관련주 강세, 네오셈, 에프에스티, 에스티아이, 유니셈 등이 상승세를 보였다.',
     'url': 'http://u/c'},
    # (d) naver_search 본문 단독 동반언급(나열형 아님) -> not relevant (출처 규칙)
    {'source': 'naver_search', 'datetime': dt.datetime(2026, 9, 15, 9, 0, tzinfo=tc.KST),
     'office': '', 'title': '라온시큐어 목표주가 상향',
     'body': '라온시큐어는 3% 상승했다. 반면 에프에스티는 약세를 보였다.', 'url': 'http://u/d'},
]
mfin = {f['url']: f for f in tn._finalize(_MENTION_ITEMS, '에프에스티')}
eq(mfin['http://u/a']['mention'], 'title', '(a) 제목 언급')
eq(mfin['http://u/a']['relevant'], True, '(a) 제목 언급 -> relevant')
eq(mfin['http://u/b']['mention'], 'body', '(b) 본문 언급')
eq(mfin['http://u/b']['list_mention'], False, '(b) 나열형 아님')
eq(mfin['http://u/b']['relevant'], True, '(b) naver_stock 본문 단독·비나열 -> relevant')
eq(mfin['http://u/c']['list_mention'], True, '(c) 콤마 4개+ 나열 -> list_mention True')
eq(mfin['http://u/c']['relevant'], False, '(c) 나열형 언급 -> not relevant')
eq(mfin['http://u/d']['mention'], 'body', '(d) naver_search 본문 언급')
eq(mfin['http://u/d']['list_mention'], False, '(d) 나열형 아님(동반언급일 뿐)')
eq(mfin['http://u/d']['relevant'], False, '(d) naver_search 본문 단독 언급은 나열형이 아니어도 not relevant')


# ==================== 4. 소스 실패 시 나머지 진행 ====================
def _boom(url, params=None, headers=None):
    raise ConnectionError('네트워크 끊김')


r5 = tn.collect_naver_stock('036810', CUTOFF, max_pages=3, fetch=_boom, delay=0)
eq(r5['status'], 'failed', '예외 발생 시 status failed')
eq('ConnectionError' in r5['reason'], True, '실패 사유에 예외 타입 기록')
eq(r5['items'], [], '첫 페이지부터 실패하면 items 는 빈 리스트')

# 1페이지는 성공, 2페이지에서 실패 -> 1페이지분은 살아남는다
r6 = tn.collect_naver_stock('036810', CUTOFF, max_pages=3,
                            fetch=_fetch_seq([_Resp(payload=STOCK_GROUP_PAGE1),
                                              ConnectionError('타임아웃')]),
                            delay=0)
eq(r6['status'], 'failed', '중간 실패도 status failed')
eq(len(r6['items']), 2, '실패 이전 페이지 items 는 보존')

# HTTP 4xx/5xx 도 failed 로 기록
r7 = tn.collect_naver_stock('036810', CUTOFF, max_pages=1,
                            fetch=_fetch_seq([_Resp(status=500)]), delay=0)
eq(r7['status'], 'failed', 'HTTP 500 은 failed')
eq('500' in r7['reason'], True, '실패 사유에 상태코드 기록')

# 검색 API 도 동일
r8 = tn.collect_naver_search('에프에스티', CUTOFF, fetch=_boom, delay=0)
eq(r8['status'], 'failed', '검색 API 예외도 failed')


# ==================== 5. 텔레그램 모듈 없음 -> skipped ====================
orig_path = list(sys.path)
r9 = tn.collect_telegram('에프에스티', tg_lib_dir='C:/이런/경로/없음')
eq(r9['status'], 'skipped', '텔레그램 모듈이 없으면 skipped')
eq(sys.path, orig_path, 'sys.path 를 원상 복구한다')


# ==================== 6. news_relevant.json (controller fix round 2) ====================
_FAKE_PAYLOAD = {
    'stock': '에프에스티', 'code': '036810', 'collected_at': 'x', 'cutoff': 'y',
    'sources': {'naver_stock': {'status': 'ok'}}, 'counts': {'total': 3, 'relevant': 2, 'reaction': 1},
    'items': [
        {'nid': 'N0001', 'source': 'naver_stock', 'relevant': True, 'type': 'news', 'body': 'a'},
        {'nid': 'N0002', 'source': 'naver_search', 'relevant': True, 'type': 'reaction', 'body': 'b'},
        {'nid': 'N0003', 'source': 'naver_search', 'relevant': False, 'type': 'news', 'body': 'c'},
    ],
}
rel = tn._relevant_payload(_FAKE_PAYLOAD)
eq([i['nid'] for i in rel['items']], ['N0001', 'N0002'], 'relevant==true 항목만 남는다 (news/reaction 모두 포함)')
eq(all(len(i['body']) <= 300 for i in rel['items']), True, 'body 는 300자 이하 그대로 유지')
eq(rel['counts'], _FAKE_PAYLOAD['counts'], 'counts 는 원본(전체) 값을 그대로 복사')
eq('news.json' in rel['note'], True, '전체 목록 위치를 note 로 안내')
eq(_FAKE_PAYLOAD['items'], [
    {'nid': 'N0001', 'source': 'naver_stock', 'relevant': True, 'type': 'news', 'body': 'a'},
    {'nid': 'N0002', 'source': 'naver_search', 'relevant': True, 'type': 'reaction', 'body': 'b'},
    {'nid': 'N0003', 'source': 'naver_search', 'relevant': False, 'type': 'news', 'body': 'c'},
], '원본 payload 는 변형되지 않는다(news.json 불변)')

# 원자적 쓰기: tc.write_json 을 그대로 쓰므로 임시파일이 남지 않고 왕복 일치한다
import tempfile                                            # noqa: E402
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, 'news_relevant.json')
    tc.write_json(p, rel)
    eq(tc.read_json(p), rel, 'write_json 왕복 후 내용 일치')
    eq(sorted(os.listdir(td)), ['news_relevant.json'], '임시파일(.tmp_*) 없이 최종 파일만 남는다')


print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_collect_news 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
