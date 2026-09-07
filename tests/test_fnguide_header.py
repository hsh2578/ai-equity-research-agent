"""fnguide_header 모듈 테스트 (2026-09 신설 -- fnguide_data 와 동일한 사고 복구)

실행: python tests/test_fnguide_header.py
     python tests/test_fnguide_header.py --net   (네트워크 실측 추가)

배경:
  fnguide_header.py 는 fnguide_data.py 와 **똑같은 병**으로 죽어 있었다.
  구 URL `comp.fnguide.com/SVO2/ASP/SVD_Main.asp|SVD_Finance.asp` 가 HTTP 200 으로
  1,829바이트짜리 "페이지가 없습니다" 를 돌려주는데 `except Exception: return {}` 가
  그것을 삼켰다. 그 결과:
    get_fnguide_header('041510')   -> {}
    get_fnguide_cashflow('041510') -> {}
  이고 financial_summary.py:121 이 이걸 호출하므로 KR 재무 요약의
  Forward PER / 업종 PER / 배당수익률 / 현금흐름이 조용히 비어 있었다.

그래서 이 테스트는 "파싱이 되는가" 뿐 아니라 **"실패를 실패라고 말하는가"** 를 본다.
픽스처: tests/fixtures/fnguide_*.html (fnguide_data 테스트와 공용, 네트워크 불필요).
"""
import sys
import os
import re

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
FIX = os.path.join(HERE, 'fixtures')

import fnguide_header as fh
from fnguide_header import (
    FnGuideError, get_fnguide_header, get_fnguide_cashflow,
    parse_header_page, parse_cashflow_page,
)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def close(actual, expected, name, tol=0.01):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected} (+-{tol})\n      실제: {actual}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


def raises(fn, reason, name):
    global _passed
    try:
        fn()
    except FnGuideError as e:
        if e.reason == reason:
            _passed += 1
        else:
            _failed.append(f"{name}\n      기대 reason: {reason}\n      실제 reason: {e.reason} ({e})")
        return
    except Exception as e:
        _failed.append(f"{name}\n      기대: FnGuideError({reason})\n      실제: {type(e).__name__}: {e}")
        return
    _failed.append(f"{name}\n      기대: FnGuideError({reason})\n      실제: 예외 없음")


def read(name):
    with open(os.path.join(FIX, name), encoding='utf-8') as f:
        return f.read()


err_html = read('fnguide_error_page.html')
sm_snp = read('fnguide_041510_snapshot.html')
sm_fin = read('fnguide_041510_finance.html')
km_snp = read('fnguide_161890_snapshot.html')
km_fin = read('fnguide_161890_finance.html')
bank_fin = read('fnguide_055550_finance.html')

# validate_page 를 통과하지만 헤더 지표가 하나도 없는 페이지 (조용한 성공 금지 검증용)
blank_ok = ('<html><head><title>에스엠(041510) | Company Guide</title></head><body>'
            + '<p>정상 응답이지만 지표가 없다.</p>' * 300 + '</body></html>')


def fake_fetch(pages):
    """{(page경로소문자, 종목코드): (status, text)} -> (url, params, timeout) 시그니처 fetch"""
    def _f(url, params, timeout=20):
        code = str(params.get('cmp_cd', ''))
        page = url.rstrip('/').rsplit('/', 1)[-1].lower()
        if (page, code) in pages:
            return pages[(page, code)]
        return (404, '<html><body>페이지가 없습니다</body></html>')
    return _f


SM_PAGES = {('snapshot', '041510'): (200, sm_snp), ('finance', '041510'): (200, sm_fin)}
KM_PAGES = {('snapshot', '161890'): (200, km_snp), ('finance', '161890'): (200, km_fin)}
ALL_PAGES = dict(SM_PAGES)
ALL_PAGES.update(KM_PAGES)
ALL_PAGES[('finance', '055550')] = (200, bank_fin)


# ============================================================================
# 0. 회귀 방어 -- 죽은 구 URL 을 다시 쓰면 즉시 실패
# ============================================================================

src = open(os.path.join(HERE, '..', 'scripts', 'fnguide_header.py'), encoding='utf-8').read()
# 사고 기록 docstring 에는 구 URL 이 남아 있어야 하므로 문자열 리터럴은 제외하고 코드만 본다
code_only = re.sub(r'("""|\'\'\')(?:.|\n)*?\1', '', src)
falsy(re.search(r'comp\.fnguide\.com/SVO2', code_only),
      '구 URL comp.fnguide.com/SVO2/ASP/*.asp 를 코드에서 더 이상 쓰지 않는다')
truthy('wcomp.fnguide.com' in src or 'fnguide_data' in src,
       '신 주소(wcomp) 또는 fnguide_data 재사용으로 전환됐다')


# ============================================================================
# 1. 실패 감지 -- 조용히 실패하지 않는가
# ============================================================================

raises(lambda: parse_header_page(err_html, '041510', status=200),
       'error_page', '헤더: 구 URL 에러 페이지 감지')
raises(lambda: parse_cashflow_page(err_html, '041510', status=200),
       'error_page', '현금흐름: 구 URL 에러 페이지 감지')

raises(lambda: parse_header_page('<html><body>ok</body></html>', '041510', status=200),
       'short_response', '헤더: 비정상적으로 짧은 응답 감지')
raises(lambda: parse_header_page(sm_snp, '041510', status=503),
       'http_status', '헤더: HTTP 503 감지')

# .aspx 리다이렉트가 늘 삼성전자를 주던 함정 -- 종목 불일치 자동 탐지
raises(lambda: parse_header_page(km_snp, '041510', status=200),
       'wrong_stock', '헤더: 요청 종목과 다른 페이지 감지')
raises(lambda: parse_cashflow_page(km_fin, '041510', status=200),
       'wrong_stock', '현금흐름: 요청 종목과 다른 페이지 감지')

# 정상 응답인데 지표가 하나도 없으면 성공으로 위장하지 않는다
raises(lambda: parse_header_page(blank_ok, '041510', status=200),
       'no_data', '헤더: 응답은 정상인데 지표가 0개면 no_data')

# FnGuideError 는 구조화된 진단을 들고 있어야 한다
try:
    parse_header_page(err_html, '041510', status=200, url='http://x')
except FnGuideError as e:
    truthy(isinstance(e.detail, dict), 'FnGuideError.detail 은 dict')
    eq(e.detail.get('page'), 'snapshot', 'FnGuideError.detail 에 page 기록')
    truthy('length' in e.detail, 'FnGuideError.detail 에 응답 길이 기록')
    truthy('status' in e.detail, 'FnGuideError.detail 에 HTTP status 기록')
    eq(e.detail.get('code'), '041510', 'FnGuideError.detail 에 종목코드 기록')


# ============================================================================
# 2. 헤더 지표 파싱 (financial_summary.py 가 쓰는 계약)
# ============================================================================

hdr = parse_header_page(sm_snp, '041510')
close(hdr['per'], 5.22, '에스엠 헤더 PER')
close(hdr['per_12m'], 12.93, '에스엠 12M Forward PER (financial_summary per_12m_forward)')
close(hdr['sector_per'], 29.65, '에스엠 업종 PER')
close(hdr['pbr'], 1.80, '에스엠 헤더 PBR')
close(hdr['dividend_yield'], 2.05, '에스엠 배당수익률')
truthy(set(hdr) <= {'per', 'per_12m', 'sector_per', 'pbr', 'dividend_yield'},
       '헤더 반환 키가 구 계약과 동일 (financial_summary 호출부 무수정)')
truthy(all(isinstance(v, float) for v in hdr.values()), '헤더 값은 전부 float')

hdr_km = parse_header_page(km_snp, '161890')
truthy(hdr_km['pbr'] != hdr['pbr'], '한국콜마 PBR != 에스엠 PBR (기본 페이지 함정 미발생)')


# ============================================================================
# 3. 현금흐름 파싱 (구 계약: ocf / invest_cf / finance_cf, 억원)
# ============================================================================

cf = parse_cashflow_page(sm_fin, '041510')
truthy(set(cf) >= {'ocf', 'invest_cf', 'finance_cf'}, '현금흐름 반환 키가 구 계약과 동일')
close(cf['ocf']['2025/12'], 1948.61, '에스엠 2025 영업활동현금흐름 1,949억')
close(cf['ocf']['2024/12'], 1356.76, '에스엠 2024 영업활동현금흐름')
close(cf['invest_cf']['2025/12'], -1500.26, '에스엠 2025 투자활동현금흐름')
close(cf['finance_cf']['2025/12'], -334.76, '에스엠 2025 재무활동현금흐름')
eq(sorted(cf['ocf']), ['2023/12', '2024/12', '2025/12'], '연간 현금흐름 3개년 라벨')
falsy([k for k in cf['ocf'] if not k.endswith('/12')], '연간에 분기 누적 컬럼 미혼입')

cf_km = parse_cashflow_page(km_fin, '161890')
truthy(cf_km['ocf']['2025/12'] != cf['ocf']['2025/12'],
       '한국콜마 OCF != 에스엠 OCF (종목별 페이지 확인)')

# 금융업(신한지주)도 계정명이 달라도 현금흐름은 잡힌다
cf_bank = parse_cashflow_page(bank_fin, '055550')
truthy(cf_bank['ocf'].get('2025/12'), '금융업 영업활동현금흐름 파싱')


# ============================================================================
# 4. 수집 함수 -- 실패를 삼키지 않고, 성공은 구 계약대로 반환
# ============================================================================

fh.LAST_ERRORS.clear()
out = get_fnguide_header('041510', fetch=fake_fetch(ALL_PAGES))
close(out.get('per_12m'), 12.93, 'get_fnguide_header: 헤더 지표 반환')
falsy(fh.LAST_ERRORS, '성공 시 에러 기록 없음')

out_km = get_fnguide_header('161890', fetch=fake_fetch(ALL_PAGES))
truthy(out_km.get('pbr') != out.get('pbr'),
       'get_fnguide_header: 041510 / 161890 이 서로 다른 값 (기본 페이지 함정 미발생)')

cf_out = get_fnguide_cashflow('041510', fetch=fake_fetch(ALL_PAGES))
close(cf_out['ocf']['2025/12'], 1948.61, 'get_fnguide_cashflow: 연간 OCF 반환')
cf_out_km = get_fnguide_cashflow('161890', fetch=fake_fetch(ALL_PAGES))
truthy(cf_out_km['ocf']['2025/12'] != cf_out['ocf']['2025/12'],
       'get_fnguide_cashflow: 두 종목이 서로 다른 값')

# 구 시그니처 하위호환 (financial_summary 는 report_type 을 넘기지 않지만 CLI 는 넘겼다)
cf_pos = get_fnguide_cashflow('041510', 'D', fetch=fake_fetch(ALL_PAGES))
eq(cf_pos['ocf'], cf_out['ocf'], 'get_fnguide_cashflow(code, "D") 구 시그니처 유지')

# 실패: 구 URL 처럼 200 + 에러페이지를 받으면 {} 를 주되 **왜인지 남긴다**
fh.LAST_ERRORS.clear()
bad = get_fnguide_header('041510', retry=1,
                         fetch=lambda *a, **k: (200, err_html))
eq(bad, {}, '헤더 수집 실패 시 빈 dict 반환 (호출자 무수정)')
truthy(fh.LAST_ERRORS, '헤더 수집 실패 시 LAST_ERRORS 에 진단 축적')
eq(fh.LAST_ERRORS[-1]['reason'], 'error_page', 'LAST_ERRORS 에 실패 사유 기록')
truthy(fh.LAST_ERRORS[-1].get('code') == '041510', 'LAST_ERRORS 에 종목코드 기록')

fh.LAST_ERRORS.clear()
bad_cf = get_fnguide_cashflow('041510', retry=1,
                              fetch=lambda *a, **k: (200, err_html))
eq(bad_cf, {}, '현금흐름 수집 실패 시 빈 dict 반환')
eq(fh.LAST_ERRORS[-1]['reason'], 'error_page', '현금흐름 실패 사유 기록')

# 네트워크 예외도 삼키지 않는다
fh.LAST_ERRORS.clear()
import requests as _rq
bad_net = get_fnguide_header('041510', retry=1,
                             fetch=lambda *a, **k: (_ for _ in ()).throw(
                                 _rq.RequestException('연결 실패')))
eq(bad_net, {}, '네트워크 예외 시 빈 dict 반환')
truthy(fh.LAST_ERRORS, '네트워크 예외도 LAST_ERRORS 에 기록')

# strict 모드는 예외를 그대로 던진다
os.environ['FNGUIDE_STRICT'] = '1'
try:
    raises(lambda: get_fnguide_header('041510', retry=1, fetch=lambda *a, **k: (200, err_html)),
           'error_page', 'FNGUIDE_STRICT=1 이면 예외를 던진다')
finally:
    os.environ.pop('FNGUIDE_STRICT', None)


# ============================================================================
# 5. financial_summary 호출부 계약
# ============================================================================

import financial_summary as fs
truthy(fs.get_fnguide_header is get_fnguide_header,
       'financial_summary 가 fallback stub 이 아니라 실제 fnguide_header 를 import')
truthy(fs.get_fnguide_cashflow is get_fnguide_cashflow,
       'financial_summary 가 실제 get_fnguide_cashflow 를 import')


# ============================================================================
# 네트워크 실측 (기본 스킵)
# ============================================================================

def net_tests():
    print('\n  [네트워크 실측]')
    seen_hdr, seen_cf = {}, {}
    for code in ['041510', '161890', '005930']:
        h = get_fnguide_header(code)
        truthy(h, f'net: get_fnguide_header({code}) 비어있지 않음')
        truthy(h.get('pbr'), f'net: {code} PBR 존재')
        c = get_fnguide_cashflow(code)
        truthy(c.get('ocf'), f'net: get_fnguide_cashflow({code}) OCF 존재')
        seen_hdr[code] = h.get('pbr')
        seen_cf[code] = max(c['ocf'].values()) if c.get('ocf') else None
        print(f'    {code}: header={h} ocf={c.get("ocf")}')
    vals = [v for v in seen_hdr.values() if v]
    eq(len(set(vals)), len(vals), 'net: 3종목 PBR 이 모두 서로 다름 (기본 페이지 함정 미발생)')
    vals = [v for v in seen_cf.values() if v]
    eq(len(set(vals)), len(vals), 'net: 3종목 OCF 가 모두 서로 다름')


if __name__ == '__main__':
    if '--net' in sys.argv:
        net_tests()

    print(f"\n  테스트: {_passed}/{_passed + len(_failed)} 통과")
    if _failed:
        print('\n  [실패]')
        for f in _failed:
            print(f'    - {f}')
        sys.exit(1)
    sys.exit(0)
