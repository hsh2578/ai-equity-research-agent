"""fnguide_data 모듈 테스트 (2026-09 신설 -- FnGuide 전면 개편 사고 후)

실행: python tests/test_fnguide_data.py
     python tests/test_fnguide_data.py --net       (네트워크 실측 테스트 추가)
     python tests/test_fnguide_data.py --refresh    (픽스처 재수집, 네트워크 필요)

배경: comp.fnguide.com/SVO2/ASP/*.asp 가 통째로 죽고 wcomp.fnguide.com 으로 이전됐는데
      `except Exception: return None` 이 실패를 삼켜서 몇 달간 아무도 몰랐다.
      data/{종목}/_fnguide.json 3건이 {"financial": null} 상태로 저장돼 있었다.
      그래서 이 테스트는 "파싱이 되는가" 뿐 아니라 **"실패를 실패라고 말하는가"** 를 검증한다.

픽스처: tests/fixtures/fnguide_*.html / *.json (실제 응답 1회 저장본).
        네트워크 없이 파서 전체를 돌린다.
"""
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
FIX = os.path.join(HERE, 'fixtures')

import fnguide_data as fg
from fnguide_data import (
    FnGuideError, validate_page, extract_init_payload, extract_tables,
    parse_finance_page, parse_consensus_page, parse_snapshot_page,
    parse_quarter_dataset, assemble_financial_data,
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
    """FnGuideError 가 지정한 reason 으로 나는지"""
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


# ============================================================================
# 픽스처 재수집 / 네트워크 테스트 (기본 스킵)
# ============================================================================

def refresh_fixtures():
    import requests
    H = dict(fg.HEADERS)
    jobs = [('041510', 'Finance'), ('041510', 'Consensus'), ('041510', 'Snapshot'),
            ('161890', 'Finance'), ('161890', 'Snapshot'),
            ('055550', 'Finance')]  # 금융업 -- 계정명 체계가 다르다
    for code, page in jobs:
        r = requests.get(f'{fg.FNGUIDE_BASE}/CompanyInfo/{page}',
                         params={'c_id': 'AA', 'menu_type': '01', 'cmp_cd': code},
                         headers=H, timeout=30)
        txt = r.content.decode('utf-8-sig', errors='replace')
        p = os.path.join(FIX, f'fnguide_{code}_{page.lower()}.html')
        open(p, 'w', encoding='utf-8').write(txt)
        print(f'  saved {p} ({len(txt)} chars)')
    for ep in ['getFinIncome', 'getFinBalance', 'getFinCashFlow']:
        r = requests.get(f'{fg.FNGUIDE_BASE}/CompanyInfo/{ep}',
                         params={'cmp_cd': '041510', 'freq_typ': 'Q', 'consol_typ': 'C'},
                         headers=H, timeout=30)
        p = os.path.join(FIX, f'fnguide_041510_{ep}_Q.json')
        open(p, 'w', encoding='utf-8').write(r.content.decode('utf-8-sig', errors='replace'))
        print(f'  saved {p}')
    r = requests.get('https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp',
                     params={'pGB': '1', 'gicode': 'A041510', 'NewMenuID': '101'},
                     headers=H, timeout=30)
    p = os.path.join(FIX, 'fnguide_error_page.html')
    open(p, 'w', encoding='utf-8').write(r.content.decode('utf-8-sig', errors='replace'))
    print(f'  saved {p} (구 URL 에러 페이지)')


def net_tests():
    """실제 네트워크 -- 3종목이 서로 다른 값을 주는지 (삼성전자 함정 탐지)"""
    print('\n  [네트워크 실측]')
    revs = {}
    for code in ['041510', '161890', '005930']:
        d = fg.get_financial_data(code)
        truthy(d, f'net: get_financial_data({code}) 결과 있음')
        if not d:
            continue
        rev = d.get('revenue_ttm')
        revs[code] = rev
        truthy(rev, f'net: {code} revenue_ttm 존재')
        eq(d.get('code'), code, f'net: {code} code 필드 일치')
        print(f'    {code}: revenue_ttm={rev} annual={sorted(d["annual"].get("revenue", {}))}')
    eq(len(set(v for v in revs.values() if v)), len([v for v in revs.values() if v]),
       'net: 3종목 revenue_ttm 이 모두 서로 다름 (삼성전자 함정 미발생)')
    for code in ['041510', '005930']:
        est = fg.get_consensus_estimates(code)
        truthy(est.get('revenue'), f'net: {code} 컨센 매출 추정 존재')


# ============================================================================
# 1. 실패 감지 -- 조용히 실패하지 않는가
# ============================================================================

err_html = read('fnguide_error_page.html')
sm_fin = read('fnguide_041510_finance.html')
sm_cns = read('fnguide_041510_consensus.html')
sm_snp = read('fnguide_041510_snapshot.html')
km_fin = read('fnguide_161890_finance.html')
km_snp = read('fnguide_161890_snapshot.html')

# 구 URL 이 주던 "페이지가 없습니다" 에러 페이지 -> 명시적 실패
raises(lambda: validate_page(err_html, '041510', status=200),
       'error_page', '에러 페이지(구 SVD_Main URL 응답) 감지')

# 짧은 응답 -> 명시적 실패
raises(lambda: validate_page('<html><body>ok</body></html>', '041510', status=200),
       'short_response', '비정상적으로 짧은 응답 감지')

# HTTP 오류 -> 명시적 실패
raises(lambda: validate_page(sm_fin, '041510', status=500),
       'http_status', 'HTTP 500 감지')

# 요청 종목과 다른 종목 페이지 -> 명시적 실패 (.aspx 가 늘 삼성전자를 주던 함정)
raises(lambda: validate_page(km_fin, '041510', status=200),
       'wrong_stock', '요청 종목코드와 다른 페이지 감지 (161890 페이지를 041510 으로 요청)')

# 정상 페이지는 통과
try:
    validate_page(sm_fin, '041510', status=200)
    validate_page(km_fin, '161890', status=200)
    _passed += 2
except Exception as e:
    _failed.append(f'정상 페이지 validate_page 통과\n      실제: {type(e).__name__}: {e}')

# FnGuideError 는 구조화된 진단을 들고 있어야 한다
try:
    validate_page(err_html, '041510', status=200, page='finance', url='http://x')
except FnGuideError as e:
    truthy(isinstance(e.detail, dict), 'FnGuideError.detail 은 dict')
    eq(e.detail.get('page'), 'finance', 'FnGuideError.detail 에 page 기록')
    truthy('length' in e.detail, 'FnGuideError.detail 에 응답 길이 기록')
    truthy('status' in e.detail, 'FnGuideError.detail 에 HTTP status 기록')

# ============================================================================
# 2. 표 개별 추출 -- 깨진 표가 있어도 전체가 죽지 않는가
# ============================================================================

tables, broken = extract_tables(sm_snp)
eq(len(tables) + len(broken), 9, 'Snapshot 표 총 9개 인식')
eq(len(broken), 2, 'Snapshot 깨진 표 2개는 건너뛴다')
eq(len(tables), 7, 'Snapshot 나머지 7개 표는 파싱된다')

# ============================================================================
# 3. 임베드 JSON 추출 (Finance/Consensus/Snapshot 은 SPA -- 표는 빈 껍데기다)
# ============================================================================

payload = extract_init_payload(sm_fin)
truthy('finIncome' in payload, 'Finance 페이지 finIncome 임베드 payload 추출')
truthy('finBalance' in payload, 'Finance 페이지 finBalance 임베드 payload 추출')
truthy('finCashFlow' in payload, 'Finance 페이지 finCashFlow 임베드 payload 추출')
eq(payload.get('cmp_cd'), '041510', 'Finance 페이지 임베드 cmp_cd')

# HTML 표만 믿으면 안 된다는 회귀 방어: Finance 표는 전부 빈 템플릿이다
fin_tables, _ = extract_tables(sm_fin)
nonnull = sum(int(t.notna().sum().sum()) for t in fin_tables[:3])
eq(nonnull, 0, 'Finance 페이지 HTML 표는 빈 템플릿 (표 파싱만으로는 데이터 0)')

# ============================================================================
# 4. 재무제표 파싱 (에스엠 041510)
# ============================================================================

fin = parse_finance_page(sm_fin, '041510')

close(fin['annual']['revenue']['2025/12'], 11749.35, '에스엠 2025 매출액 11,749억')
close(fin['annual']['revenue']['2024/12'], 9897.25, '에스엠 2024 매출액 9,897억')
close(fin['annual']['revenue']['2023/12'], 9610.70, '에스엠 2023 매출액 9,611억')
close(fin['annual']['operating_income']['2025/12'], 1830.34, '에스엠 2025 영업이익 1,830억')
close(fin['annual']['gross_profit']['2025/12'], 4325.35, '에스엠 2025 매출총이익')
close(fin['annual']['net_income']['2025/12'], 3593.64, '에스엠 2025 당기순이익')

# 연간에 '2026/06 (최근분기)' 누적 컬럼이 섞이면 안 된다 (구 코드가 늘 틀리던 지점)
falsy('2026/06' in fin['annual']['revenue'], '연간 매출에 최근분기 누적 컬럼 미혼입')
eq(sorted(fin['annual']['revenue']), ['2022/12', '2023/12', '2024/12', '2025/12'],
   '연간 매출 4개년 (표 3년 + 차트 보충 1년)')

close(fin['balance']['total_assets'], 20077.11, '에스엠 자산총계 (최근 연간 결산)', tol=1.0)
truthy(fin['balance'].get('cash'), '에스엠 현금및현금성자산 존재')
truthy(fin['cashflow'].get('cfo_annual'), '에스엠 영업활동현금흐름 연간 존재')
truthy(fin['cashflow'].get('invest_cf_annual'), '에스엠 투자활동현금흐름 연간 존재')

# 다른 종목은 다른 값이 나와야 한다
fin_km = parse_finance_page(km_fin, '161890')
truthy(fin_km['annual']['revenue']['2025/12'] != fin['annual']['revenue']['2025/12'],
       '한국콜마 매출 != 에스엠 매출 (종목별 페이지 확인)')

# 금융업(신한지주)은 계정명 체계가 다르다: '자산총계' 가 아니라 '자산'
fin_bank = parse_finance_page(read('fnguide_055550_finance.html'), '055550')
truthy(fin_bank['balance'].get('total_assets'), '금융업 자산총계 (계정명 "자산") 파싱')
truthy(fin_bank['balance'].get('total_equity'), '금융업 자본총계 (계정명 "자본") 파싱')
truthy(fin_bank['annual'].get('operating_income'), '금융업 연간 영업이익 파싱')
truthy(fin_bank['annual']['revenue'].get('2025/12'), '금융업 연간 매출(영업수익) 차트 보충')

# ============================================================================
# 5. 분기 데이터 + TTM
# ============================================================================

q_income = json.loads(read('fnguide_041510_getFinIncome_Q.json'))
q_balance = json.loads(read('fnguide_041510_getFinBalance_Q.json'))
q_cash = json.loads(read('fnguide_041510_getFinCashFlow_Q.json'))

q = parse_quarter_dataset(q_income, q_balance, q_cash)
eq(len(q['quarter']['revenue']), 4, '분기 매출 4개 분기')
eq(sorted(q['quarter']['revenue']), ['2025/09', '2025/12', '2026/03', '2026/06'],
   '분기 라벨 4개 (최근분기 포함, 전년동기/증감률 제외)')
truthy(q['balance_avg'].get('total_assets'), '4분기 평균 자산총계 산출')

snp = parse_snapshot_page(sm_snp, '041510')
data = assemble_financial_data('041510', fin, snp, q)

eq(data['code'], '041510', 'assemble: code')
close(data['revenue_ttm'],
      sum(q['quarter']['revenue'].values()), 'TTM 매출 = 최근 4분기 합', tol=0.1)
truthy(data.get('operating_income_ttm'), 'TTM 영업이익 산출')
truthy(data.get('cfo_ttm'), 'TTM 영업현금흐름 산출')
falsy(data['_meta']['warnings'], f"정상 종목은 경고 없음 (실제: {data['_meta']['warnings']})")

# ============================================================================
# 6. 헤더 지표 / Snapshot 요약
# ============================================================================

close(snp['header']['pbr'], 1.80, '에스엠 헤더 PBR')
truthy(snp['header'].get('per'), '에스엠 헤더 PER 존재')
truthy(snp['header'].get('sector_per'), '에스엠 헤더 업종 PER 존재')
eq(snp['consensus_summary']['target_price'], 113412, '에스엠 컨센 목표주가')
eq(snp['consensus_summary']['n_estimates'], 17, '에스엠 추정기관수')
truthy(snp['price'].get('market_cap'), '에스엠 시가총액 파싱')

snp_km = parse_snapshot_page(km_snp, '161890')
truthy(snp_km['header'].get('pbr') != snp['header'].get('pbr'),
       '한국콜마 PBR != 에스엠 PBR')

# ============================================================================
# 7. 컨센서스 추정
# ============================================================================

est = parse_consensus_page(sm_cns, '041510')
truthy(est.get('revenue'), '컨센 매출 추정 존재')
eq(sorted(est['revenue']), ['2026/12(E)', '2027/12(E)', '2028/12(E)'],
   '컨센 3년 추정 라벨')
close(est['revenue']['2026/12(E)'], 12605.18, '에스엠 2026E 매출')
close(est['operating_income']['2027/12(E)'], 2167.59, '에스엠 2027E 영업이익')
truthy(est.get('eps'), '컨센 EPS 추정 존재')
truthy(est.get('per'), '컨센 PER 추정 존재')
truthy(est['_meta']['actual'].get('revenue'), '컨센 페이지의 실적 실측도 함께 반환')

# ============================================================================
# 8. 핵심 필드가 비면 경고를 남기는가 (조용한 성공 금지)
# ============================================================================

empty_fin = {'annual': {}, 'quarter': {}, 'balance': {}, 'balance_avg': {},
             'cashflow': {}, 'annual_chart': {}}
empty_q = {'quarter': {}, 'balance': {}, 'balance_avg': {}, 'cashflow': {}}
d2 = assemble_financial_data('999999', empty_fin,
                             {'header': {}, 'consensus_summary': {}, 'price': {}, 'annual': {}},
                             empty_q)
truthy(any('매출' in w for w in d2['_meta']['warnings']), '매출 비면 경고 기록')
truthy(any('영업이익' in w for w in d2['_meta']['warnings']), '영업이익 비면 경고 기록')

# 실패 진단이 모듈 레벨에 남는가
fg.LAST_ERRORS.clear()
out = fg.get_financial_data('000000', retry=1, _fetch=lambda *a, **k: (_ for _ in ()).throw(
    FnGuideError('error_page', '테스트용 강제 실패', page='finance', status=200, length=10)))
eq(out, None, '수집 실패 시 None 반환')
truthy(fg.LAST_ERRORS, '수집 실패 시 LAST_ERRORS 에 진단 축적 (조용히 삼키지 않음)')
eq(fg.LAST_ERRORS[-1]['reason'], 'error_page', 'LAST_ERRORS 에 실패 사유 기록')

# 헬퍼 하위호환
eq(fg.get_ebit(data), data['operating_income_ttm'], 'get_ebit == 영업이익 TTM')
truthy(fg.get_roe(data) is not None, 'get_roe 산출')
truthy(fg.get_psr(18087, data) is not None, 'get_psr 산출')


# ============================================================================
if __name__ == '__main__':
    if '--refresh' in sys.argv:
        print('픽스처 재수집 중...')
        refresh_fixtures()
    if '--net' in sys.argv:
        net_tests()

    print(f"\n  테스트: {_passed}/{_passed + len(_failed)} 통과")
    if _failed:
        print('\n  [실패]')
        for f in _failed:
            print(f'    - {f}')
        sys.exit(1)
    sys.exit(0)
