"""collect_kirs_reports -- 한국IR협의회 보고서 수집기 테스트 (v5.22).

이 수집기가 실제로 틀렸던 두 곳을 고정한다.

  1. **상세 응답 스키마가 목록과 다르다.** 목록은 평평한 dict 인데 상세는
     본문이 `researchContent` 안에 들어 있다. 이걸 모르고 `d['attachUrl']`
     을 읽어 전편이 'attachUrl 없음' 으로 실패했다.
  2. **에러 페이지가 HTTP 200 으로 온다.** 그래서 `%PDF` 매직바이트를 본다.
     이걸 안 보면 HTML 조각이 .pdf 로 저장되고 fitz 가 뒤늦게 죽는다.

그리고 시점 계산 -- 참조 리포트는 **언제 쓴 글인지가 반이다**.
CJ프레시웨이 리포트는 21개월 전 것이라 형식은 배우되 시장 규모는 못 쓴다.

실행: python tests/test_collect_kirs_reports.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import datetime as dt                                   # noqa: E402
import collect_kirs_reports as ck                       # noqa: E402

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


# ---------- _age_months ----------
TODAY = dt.date(2026, 9, 15)
eq(ck._age_months('2024.12.16', TODAY), 21, '2024-12 는 21개월 전')
eq(ck._age_months('2026-09-01', TODAY), 0, '같은 달은 0개월')
eq(ck._age_months('2026.03.10', TODAY), 6, '반년 전은 6개월')
eq(ck._age_months('2025/06/30', TODAY), 15, '슬래시 구분자도 읽는다')
eq(ck._age_months('20260615', TODAY), 3, '구분자 없는 표기도 읽는다')
eq(ck._age_months(None, TODAY), None, '날짜가 없으면 None -- 0 으로 두면 최신으로 오판한다')
eq(ck._age_months('', TODAY), None, '빈 문자열도 None')
eq(ck._age_months('언제인지 모름', TODAY), None, '파싱 실패는 None')

# 해가 바뀌는 경계
eq(ck._age_months('2025.12.31', dt.date(2026, 1, 1)), 1, '연말/연초 경계')

# ---------- 상수 ----------
eq(ck.BROKER, '한국IR협의회', '증권사명은 정확히 일치로 거른다 (부분일치면 유사기관이 섞인다)')
eq(ck.LIST_URL.startswith('https://m.stock.naver.com'), True,
   '**목록은 kirs.or.kr 이 아니라 네이버 금융이다** (kirs 의 tech2020_* 은 NICE디앤비다)')

# ---------- download: 실패를 구조화해 돌려준다 (except: pass 금지) ----------
class _Resp:
    def __init__(self, status=200, payload=None, content=b''):
        self.status_code = status
        self._payload = payload
        self.content = content

    def json(self):
        return self._payload


class _Session:
    """requests.Session 대역. 첫 get 은 상세, 둘째 get 은 PDF."""

    def __init__(self, detail, pdf=None):
        self._detail, self._pdf, self.n = detail, pdf, 0
        self.headers = {}

    def update(self, *a, **k):
        pass

    def get(self, url, **kw):
        self.n += 1
        return self._detail if self.n == 1 else self._pdf


def run(detail, pdf=None, out_dir=None):
    orig = ck.requests.Session
    ck.requests.Session = lambda: _Session(detail, pdf)
    try:
        return ck.download(1, '테스트', out_dir=out_dir or os.devnull)
    finally:
        ck.requests.Session = orig


# 상세 HTTP 실패
eq(run(_Resp(status=500))['stage'], 'detail', '상세 5xx 는 stage=detail')

# 스키마: 본문이 researchContent 안에 있다
nested = _Resp(payload={'researchContent': {'brokerName': '한국IR협의회',
                                            'attachUrl': 'http://x/a.pdf'}})
eq(run(nested, _Resp(content=b'<html>error</html>'))['stage'], 'magic',
   '**HTML 이 200 으로 와도 %PDF 가 아니면 저장하지 않는다**')

# 다른 증권사면 거른다
other = _Resp(payload={'researchContent': {'brokerName': '다른증권',
                                           'attachUrl': 'http://x/a.pdf'}})
eq(run(other)['stage'], 'broker', '증권사가 다르면 stage=broker')

# attachUrl 이 없는 경우
noatt = _Resp(payload={'researchContent': {'brokerName': '한국IR협의회'}})
eq(run(noatt)['stage'], 'attach', 'attachUrl 이 없으면 stage=attach')

# 평평한 스키마(목록과 같은 모양)도 받아들인다
flat = _Resp(payload={'brokerName': '한국IR협의회', 'attachUrl': 'http://x/a.pdf'})
eq(run(flat, _Resp(content=b'<html>'))['stage'], 'magic',
   'researchContent 가 없으면 최상위를 본문으로 본다')

# PDF 다운로드 자체가 실패
eq(run(nested, _Resp(status=404))['stage'], 'pdf', 'PDF 4xx 는 stage=pdf')

# 정상 저장
import tempfile                                          # noqa: E402
with tempfile.TemporaryDirectory() as td:
    r = run(nested, _Resp(content=b'%PDF-1.7 ...'), out_dir=td)
    eq('path' in r, True, '정상 응답은 path 를 돌려준다')
    eq(os.path.exists(os.path.join(td, '테스트_1.pdf')), True, '파일이 실제로 생긴다')
    eq(r['bytes'], 12, '바이트 수를 함께 돌려준다')

# 파일명에 경로 문자가 들어가도 안전하다
with tempfile.TemporaryDirectory() as td:
    orig = ck.requests.Session
    ck.requests.Session = lambda: _Session(nested, _Resp(content=b'%PDF-1.7'))
    try:
        r = ck.download(2, 'A/B:C*D', out_dir=td)
    finally:
        ck.requests.Session = orig
    eq(os.path.basename(r['path']), 'ABCD_2.pdf', '경로 특수문자는 제거한다')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  collect_kirs_reports 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
