"""
FnGuide 경량 파서 -- 헤더 지표 + 현금흐름표 (wcomp.fnguide.com, 2026-09 재작성)

용도:
- KIS API가 주지 않는 12M Forward PER / 업종 PER / 배당수익률 (헤더)
- KIS API에 엔드포인트가 없는 **현금흐름표** (영업/투자/재무 CF)
- DCF 밸류에이션과 "이익의 질" 분석에 필수
- 호출자: `scripts/financial_summary.py` (STEP 1.5 KR 재무 요약)

반환 계약 (구버전과 동일 -- 호출부 무수정):
    get_fnguide_header(code)   -> {per, per_12m, sector_per, pbr, dividend_yield}
    get_fnguide_cashflow(code) -> {'ocf': {'2025/12': 1948.61, ...},
                                   'invest_cf': {...}, 'finance_cf': {...}}   # 억원
    실패 시 둘 다 빈 dict -- 단 **왜 실패했는지 stderr + LAST_ERRORS 에 남긴다.**


[주의] 2026-09 사고 기록 -- 왜 재작성했나
--------------------------------------------------------------------------
이 모듈은 `fnguide_data.py` 와 **똑같은 병**으로 죽어 있었다.
구 URL `comp.fnguide.com/SVO2/ASP/SVD_Main.asp | SVD_Finance.asp` 가

  - HTTP 200 을 주면서 1,829바이트짜리 "페이지가 없습니다" 에러 페이지를 반환
  - 신 사이트 `wcomp.fnguide.com/CompanyInfo/*` 는 SPA -- HTML <table> 이 전부
    빈 템플릿이고 실제 데이터는 `finance.init({...})` 임베드 JSON 에 있다

그런데 구버전이 `except Exception: return {}` 로 실패를 통째로 삼켰다. 실측:
    get_fnguide_header('041510')   -> {}
    get_fnguide_cashflow('041510') -> {}
financial_summary.py:121 이 이걸 호출하므로 KR 재무 요약의 Forward PER / 업종 PER /
배당수익률 / 현금흐름이 **조용히 비어 있었고 몇 달간 아무도 몰랐다.**

그래서 이 재작성본은 파싱 로직을 직접 갖지 않고, 이미 고쳐진 정본
`fnguide_data.py` 의 검증·파싱 헬퍼를 **재사용**한다 (중복 구현 = 중복 사고).
  - validate_page()        : HTTP status / 에러페이지 마커 / 응답 길이 / 종목 불일치
  - parse_header_metrics() : 신 마크업(button.tip_in + 다음 <li>) 헤더 지표
  - parse_finance_page()   : finCashFlow 임베드 JSON -> 연간 현금흐름
그리고 실패는 `FnGuideError(reason, ...)` 로 구조화해 stderr + LAST_ERRORS 에 남긴다.
`FNGUIDE_STRICT=1` 이면 빈 dict 대신 예외를 던진다.

되찾은 것 / 못 되찾은 것 (신 사이트 한계, 2026-09 실측):
  - 헤더 5종(PER / 12M Forward PER / 업종 PER / PBR / 배당수익률): **전부 복구**
  - 연간 현금흐름 영업/투자/재무: 복구. 단 **3개년** (구 SVD_Finance 는 5개년)
  - CapEx(유형자산의취득): 구버전도 못 뽑았고 신 dataset 요약에도 없다 -- 여전히 없음
  - 분기 현금흐름: 이 경량 모듈 범위 밖. 필요하면 fnguide_data.get_financial_data()
    의 `cashflow['cfo_quarter']` 를 쓸 것.
--------------------------------------------------------------------------
"""

import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 정본 모듈 재사용 (재구현 금지 -- 중복 구현이 이 사고의 원인이었다)
from fnguide_data import (  # noqa: E402
    DEFAULT_TIMEOUT,
    FNGUIDE_BASE,
    PAGE_PATH,
    FnGuideError,
    _fetch_page,
    _record_error,
    _record_warning,
    _strict,
    parse_finance_page,
    parse_header_metrics,
    validate_page,
)
from fnguide_data import LAST_ERRORS, LAST_WARNINGS  # noqa: E402  (동일 진단 싱크 공유)

__all__ = [
    'FnGuideError', 'LAST_ERRORS', 'LAST_WARNINGS',
    'HEADER_KEYS', 'CF_KEY_MAP',
    'parse_header_page', 'parse_cashflow_page',
    'get_fnguide_header', 'get_fnguide_cashflow',
]

# financial_summary.py 가 기대하는 헤더 키 (구 계약 유지)
HEADER_KEYS = ('per', 'per_12m', 'sector_per', 'pbr', 'dividend_yield')

# fnguide_data 의 현금흐름 키 -> 이 모듈의 구 계약 키
CF_KEY_MAP = {
    'cfo_annual': 'ocf',
    'invest_cf_annual': 'invest_cf',
    'fin_cf_annual': 'finance_cf',
}


# ============================================================================
# 파서 (네트워크 없이 테스트 가능)
# ============================================================================

def parse_header_page(html: str, code: str, status: int = 200,
                      url: str = '') -> Dict[str, float]:
    """/CompanyInfo/Snapshot HTML -> 헤더 지표 5종.

    검증 실패(에러페이지/짧은 응답/HTTP 오류/종목 불일치)나 지표 0개면 FnGuideError.
    """
    validate_page(html, code, status=status, page='snapshot', url=url)
    metrics = parse_header_metrics(html)
    if not metrics:
        raise FnGuideError(
            'no_data',
            '응답은 정상인데 헤더 지표(PER/PBR/배당수익률)를 하나도 찾지 못했다 '
            '-- 마크업이 또 바뀌었을 수 있다',
            code=code, page='snapshot', url=url, status=status, length=len(html or ''))
    return {k: float(v) for k, v in metrics.items() if k in HEADER_KEYS}


def parse_cashflow_page(html: str, code: str, status: int = 200,
                        url: str = '') -> Dict[str, Dict[str, float]]:
    """/CompanyInfo/Finance HTML -> 연간 현금흐름 (억원, 구 계약 키).

    Returns:
        {'ocf': {'2025/12': 1948.61, ...}, 'invest_cf': {...}, 'finance_cf': {...}}
    """
    fin = parse_finance_page(html, code, status=status, url=url)
    raw = fin.get('cashflow') or {}

    out: Dict[str, Dict[str, float]] = {'ocf': {}, 'invest_cf': {}, 'finance_cf': {}}
    for src_key, dst_key in CF_KEY_MAP.items():
        for period, val in (raw.get(src_key) or {}).items():
            if val is None:
                continue
            out[dst_key][str(period)] = float(val)

    if not out['ocf']:
        raise FnGuideError(
            'no_data',
            '응답은 정상인데 연간 영업활동현금흐름을 찾지 못했다 '
            '(finCashFlow 임베드 dataset 이 비었거나 계정명이 바뀌었다)',
            code=code, page='finance', url=url, status=status, length=len(html or ''))

    for dst_key in ('invest_cf', 'finance_cf'):
        if not out[dst_key]:
            _record_warning(f'{code}: 연간 {dst_key} 가 비었다 (영업CF는 정상)')
    return out


# ============================================================================
# 수집
# ============================================================================

def _collect(code: str, page: str, parser: Callable[..., Any], label: str,
             retry: int, fetch, timeout: int, empty):
    """공통 수집 루프. 실패는 삼키지 않고 LAST_ERRORS + stderr 에 남긴다."""
    last_err: Optional[FnGuideError] = None
    url = FNGUIDE_BASE + PAGE_PATH[page]

    for attempt in range(max(1, retry)):
        try:
            html = _fetch_page(code, page, fetch, timeout)
            return parser(html, code, status=200, url=url)
        except FnGuideError as e:
            last_err = e
        except Exception as e:  # 예상 못 한 실패도 삼키지 않는다
            last_err = FnGuideError('unexpected', f'{type(e).__name__}: {e}',
                                    code=code, page=page, url=url)
        if attempt < retry - 1:
            time.sleep(0.5)

    if last_err is not None:
        _record_error(last_err)
        print(f'[FNGUIDE][ERROR] {code} {label} 수집 실패 -- 빈 값으로 진행한다. '
              f'financial_summary 의 해당 항목이 빈다.', file=sys.stderr)
        if _strict():
            raise last_err
    return empty


def get_fnguide_header(code: str, timeout: int = DEFAULT_TIMEOUT,
                       retry: int = 2, fetch=None) -> Dict[str, float]:
    """FnGuide Snapshot 페이지에서 헤더 지표만 추출.

    Returns:
        {per, per_12m, sector_per, pbr, dividend_yield} -- 실패 시 빈 dict.
        (실패 사유는 stderr + LAST_ERRORS)

    Args:
        fetch: 테스트 주입용 `(url, params, timeout) -> (status, text)`
    """
    result = _collect(code, 'snapshot', parse_header_page, '헤더 지표',
                      retry, fetch, timeout, {})
    if result:
        missing = [k for k in ('per_12m', 'sector_per', 'dividend_yield') if k not in result]
        if missing:
            _record_warning(f'{code}: 헤더 지표 일부 결측 {missing}')
    return result


def get_fnguide_cashflow(code: str, report_type: str = 'D',
                         timeout: int = DEFAULT_TIMEOUT, retry: int = 2,
                         fetch=None) -> Dict[str, Dict[str, float]]:
    """FnGuide Finance 페이지에서 연간 현금흐름표 추출.

    Args:
        code: 6자리 종목코드
        report_type: 구 시그니처 호환용. 신 페이지는 연결(C)만 제공하므로 무시된다.
                     'I'(개별)를 주면 경고를 남기고 연결값을 돌려준다.

    Returns:
        {'ocf': {'2025/12': ...}, 'invest_cf': {...}, 'finance_cf': {...}}  (억원)
        실패 시 빈 dict. (실패 사유는 stderr + LAST_ERRORS)
    """
    if report_type and report_type.upper() != 'D':
        _record_warning(
            f'{code}: report_type={report_type!r} 는 신 FnGuide 에서 지원되지 않는다 '
            '-- 연결(consol) 기준 값을 반환한다')
    return _collect(code, 'finance', parse_cashflow_page, '연간 현금흐름',
                    retry, fetch, timeout, {})


# ============================================================================
# CLI
# ============================================================================

def _cli(argv: List[str]) -> int:
    code = argv[1] if len(argv) > 1 else '000270'

    print(f'=== {code} FnGuide 헤더 ===')
    h = get_fnguide_header(code)
    if not h:
        print('[FAIL] 헤더 추출 실패 -- 위 진단을 확인하라')
    else:
        for k in HEADER_KEYS:
            if k in h:
                print(f'  {k}: {h[k]}')

    print(f'\n=== {code} FnGuide 현금흐름표 (연간, 억원) ===')
    cf = get_fnguide_cashflow(code)
    if not cf or not cf.get('ocf'):
        print('[FAIL] 현금흐름 추출 실패 -- 위 진단을 확인하라')
    else:
        print('  연도            OCF       투자CF       재무CF')
        for y in sorted(cf['ocf']):
            print(f"  {y}  {cf['ocf'].get(y, 0):>11,.0f}  "
                  f"{cf['invest_cf'].get(y, 0):>11,.0f}  "
                  f"{cf['finance_cf'].get(y, 0):>11,.0f}")

    return 0 if (h and cf.get('ocf')) else 1


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(_cli(sys.argv))
