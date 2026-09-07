"""
FnGuide 재무제표 수집 모듈 (wcomp.fnguide.com, 2026-09 전면 재작성)

수집 데이터:
- 연간/분기 손익계산서: 매출액, 매출총이익, 영업이익, 당기순이익, 법인세, 금융원가
- 연간/분기 재무상태표: 자산/자본/유동/비유동/현금/차입금/재고 등
- 연간/분기 현금흐름표: 영업/투자/재무활동현금흐름
- 페이지 헤더: PER, 12M PER, 업종 PER, PBR, 배당수익률
- Snapshot 요약: 투자의견/목표주가/컨센 EPS/PER/추정기관수, 시총/52주/베타
- 컨센서스 3년 추정: 매출/영업이익/순이익/EPS/BPS/DPS/PER/PBR/자산/부채/자본

사용법:
    from fnguide_data import get_financial_data, get_consensus_estimates
    data = get_financial_data('041510')
    est  = get_consensus_estimates('041510')

CLI (stdout = JSON, stderr = 진단):
    python scripts/fnguide_data.py 041510 > data/에스엠/_fnguide.json


[주의] 2026-09 사고 기록 -- 왜 전면 재작성했나
--------------------------------------------------------------------------
구버전은 `comp.fnguide.com/SVO2/ASP/SVD_Main.asp` / `SVD_Finance.asp` 를 읽고
`pd.read_html()` 로 표를 파싱했다. FnGuide 가 `wcomp.fnguide.com` 으로 이전하면서

  1. 구 URL 은 HTTP 200 을 주면서 1.8KB짜리 "페이지가 없습니다" 에러 페이지를 반환
  2. `.aspx` 로 바꾸면 리다이렉트는 되지만 gicode 가 무시되어 **항상 삼성전자**를 반환
  3. 신 페이지는 SPA -- HTML 의 <table> 은 전부 빈 템플릿이고 데이터는
     `finance.init({...})` 임베드 JSON / AJAX JSON 엔드포인트에 있다

그런데 구버전 코드가 `except Exception: return None` 으로 실패를 통째로 삼켰고,
호출자는 `{"financial": null}` 을 그냥 저장했다. **몇 달간 아무도 몰랐다.**

그래서 이 모듈은 실패를 절대 조용히 넘기지 않는다:
  - `FnGuideError(reason, message, **detail)` 로 실패 사유를 구조화한다
    (reason: network / http_status / error_page / short_response / wrong_stock /
             no_payload / no_data / bad_json)
  - 응답이 5,000바이트 미만이거나 "페이지가 없습니다" 를 포함하면 즉시 실패 처리
  - 응답 <title> 에 요청한 종목코드가 없으면 즉시 실패 처리 (삼성전자 함정 자동 탐지)
  - 성공해도 매출/영업이익 등 핵심 필드가 비면 `_meta['warnings']` 에 남기고 stderr 경고
  - 실패 진단은 모듈 전역 `LAST_ERRORS` 에 축적되고 stderr 에 블록으로 출력된다
  - `FNGUIDE_STRICT=1` 환경변수를 주면 None 대신 예외를 던진다

되찾은 것 / 못 되찾은 것 (신 사이트 한계, 2026-09 실측):
  - 연간 실적: 표 3개년 + 차트 엔드포인트 1개년 = **최대 4개년** (구 5개년에서 축소).
    매출/영업이익/당기순이익만 4개년이고 나머지 계정은 3개년이다.
  - 컨센 추정: 3개년 (매출/영업이익/순이익/EPS/BPS/DPS/PER/PBR/자산/부채/자본) -- 그대로 확보.
    단 **ROE 추정치는 신 컨센 데이터셋에 없다** (`_meta['unavailable']` 참조).
  - 분기 실측: 4개 분기 -- 그대로 확보.
--------------------------------------------------------------------------
"""

import io
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
import pandas as pd
import requests

# ============================================================================
# 상수
# ============================================================================

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'X-Requested-With': 'XMLHttpRequest',
}

FNGUIDE_BASE = 'https://wcomp.fnguide.com'

# 화면 구분은 menu_type 이 아니라 **경로**다 (구 NewMenuID=101/103 대응)
PAGE_PATH = {
    'snapshot':  '/CompanyInfo/Snapshot',       # 투자의견/목표주가/헤더 PER/PBR
    'finance':   '/CompanyInfo/Finance',        # 재무제표 (연간 3년 + 최근분기)
    'consensus': '/CompanyInfo/Consensus',      # 컨센서스 3년 추정
    'ratio':     '/CompanyInfo/FinanceRatio',   # 재무비율
}
AJAX_BASE = FNGUIDE_BASE + '/CompanyInfo/'

# 에러 페이지 자동 감지
MIN_PAGE_BYTES = 5000
ERROR_MARKERS = (
    '페이지가 없습니다',
    '페이지를 찾을 수 없',
    '일시적으로 서비스',
    'class="error_wrap"',
)

DEFAULT_TIMEOUT = 20

# 실패 진단 축적 (조용한 실패 금지 -- 호출자/테스트가 사후 확인 가능)
LAST_ERRORS: List[Dict[str, Any]] = []
LAST_WARNINGS: List[str] = []


# ---- 계정명 매핑 (신 JSON dataset 의 NAME 은 정확 일치로 잡는다) --------------

INCOME_MAP = {
    '매출액(수익)': 'revenue',
    '매출액': 'revenue',
    '영업수익': 'revenue',
    '매출총이익': 'gross_profit',
    '영업이익': 'operating_income',
    '당기순이익': 'net_income',
    '(지배주주지분)당기순이익': 'net_income_controlling',
    '지배주주순이익': 'net_income_controlling',
    '법인세비용': 'tax_expense',
    '금융원가': 'finance_cost',
}

BALANCE_MAP = {
    '자산총계': 'total_assets',
    '자본총계': 'total_equity',
    # 금융업(은행/지주/보험)은 '자산총계' 가 아니라 '자산/부채/자본' 으로 표기한다.
    # 제조업 dataset 에는 이 짧은 이름이 아예 없으므로 정확 일치 별칭으로 안전하다.
    '자산': 'total_assets',
    '부채': 'total_liabilities',
    '자본': 'total_equity',
    '지배주주지분': 'controlling_equity',
    '유동자산': 'current_assets',
    '유동부채': 'current_liabilities',
    '비유동자산': 'non_current_assets',
    '비유동부채': 'non_current_liabilities',
    '부채총계': 'total_liabilities',
    '현금및현금성자산': 'cash',
    '단기금융자산': 'short_term_fin_assets',
    '단기차입금': 'short_term_debt',
    '장기차입금': 'long_term_debt',
    '사채': 'bonds',
    '재고자산': 'inventory',
}

CASHFLOW_MAP = {
    '영업활동으로인한현금흐름': 'cfo',
    '투자활동으로인한현금흐름': 'invest_cf',
    '재무활동으로인한현금흐름': 'fin_cf',
}

# getFinIncomeMajorChart (연간 4개년 -- 표보다 1년 더 길다)
CHART_MAP = {
    '매출액': 'revenue',
    '영업이익': 'operating_income',
    '당기순이익': 'net_income',
}

# 컨센서스 perforTrend
CONSENSUS_MAP = {
    '매출액': 'revenue',
    '영업이익': 'operating_income',
    '당기순이익': 'net_income',
    '당기순이익(지배)': 'net_income_controlling',
    '자산총계': 'total_assets',
    '부채총계': 'total_liabilities',
    '자본총계': 'total_equity',
    '자본총계(지배)': 'controlling_equity',
    '자본금': 'capital_stock',
    'EPS': 'eps',
    'BPS': 'bps',
    '현금DPS': 'dps',
    'PER': 'per',
    'PBR': 'pbr',
}

# Snapshot 임베드 snpFinancial (연간) -- 표에 없는 비율 지표 보충
SNP_ANNUAL_MAP = {
    'EPS': 'eps',
    'BPS': 'bps',
    '현금DPS': 'dps',
    'ROE': 'roe',
    'ROA': 'roa',
    '영업이익률': 'operating_margin',
    '부채비율': 'debt_ratio',
    '발행주식수(보통주)': 'shares_outstanding',
}

# 페이지 헤더 지표 ID 매핑
HEADER_METRIC_IDS = {
    'h_per': 'per',
    'h_12m': 'per_12m',
    'h_u_per': 'sector_per',
    'h_pbr': 'pbr',
    'h_rate': 'dividend_yield',
}


# ============================================================================
# 실패 표현
# ============================================================================

class FnGuideError(Exception):
    """FnGuide 수집 실패. 왜 실패했는지를 구조화해 들고 다닌다."""

    def __init__(self, reason: str, message: str, **detail):
        self.reason = reason
        self.detail = dict(detail)
        self.detail.setdefault('reason', reason)
        super().__init__(f'[{reason}] {message}')
        self.message = message

    def as_dict(self) -> Dict[str, Any]:
        d = dict(self.detail)
        d['reason'] = self.reason
        d['message'] = self.message
        return d


def _record_error(err: FnGuideError) -> None:
    rec = err.as_dict()
    rec['ts'] = time.strftime('%Y-%m-%d %H:%M:%S')
    LAST_ERRORS.append(rec)
    lines = [
        '[FNGUIDE][ERROR] 수집 실패 -- 조용히 넘기지 않는다',
        f"  사유      : {rec.get('reason')}",
        f"  메시지    : {rec.get('message')}",
    ]
    for k in ('code', 'page', 'endpoint', 'url', 'status', 'length', 'title',
              'tables_ok', 'tables_broken'):
        if rec.get(k) is not None:
            lines.append(f'  {k:<10}: {rec[k]}')
    print('\n'.join(lines), file=sys.stderr)


def _record_warning(msg: str) -> None:
    LAST_WARNINGS.append(msg)
    print(f'[FNGUIDE][WARN] {msg}', file=sys.stderr)


def _strict() -> bool:
    return os.environ.get('FNGUIDE_STRICT', '').strip() not in ('', '0', 'false', 'False')


# ============================================================================
# 저수준: 수집 + 검증
# ============================================================================

def _http_get(url: str, params: Dict[str, str], timeout: int = DEFAULT_TIMEOUT) -> Tuple[int, str]:
    """(status_code, text). FnGuide 는 charset 헤더가 없는 응답이 있어 utf-8 강제 디코드."""
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    except requests.RequestException as e:
        raise FnGuideError('network', f'HTTP 요청 실패: {e}', url=url,
                           params=dict(params), status=None, length=0)
    return resp.status_code, resp.content.decode('utf-8-sig', errors='replace')


def parse_page_title(html: str) -> str:
    m = re.search(r'<title>(.*?)</title>', html or '', re.S | re.I)
    return m.group(1).strip() if m else ''


def validate_page(html: str, code: str, status: int = 200,
                  page: str = '', url: str = '') -> str:
    """페이지 응답이 '요청한 종목의 정상 페이지' 인지 검증. 아니면 FnGuideError.

    검사 순서 (앞의 것이 더 구체적):
      1. HTTP status != 200                 -> http_status
      2. 에러 페이지 마커 포함              -> error_page
      3. 응답 길이 < MIN_PAGE_BYTES         -> short_response
      4. <title> 에 요청 종목코드 없음      -> wrong_stock  (.aspx 삼성전자 함정)
    """
    html = html or ''
    detail = {'code': code, 'page': page, 'url': url,
              'status': status, 'length': len(html)}

    if status != 200:
        raise FnGuideError('http_status', f'HTTP {status}', **detail)

    for marker in ERROR_MARKERS:
        if marker in html:
            raise FnGuideError('error_page',
                               f'FnGuide 에러 페이지 감지 (marker={marker!r})',
                               title=parse_page_title(html), **detail)

    if len(html) < MIN_PAGE_BYTES:
        raise FnGuideError('short_response',
                           f'응답이 비정상적으로 짧다 ({len(html)} < {MIN_PAGE_BYTES} bytes)',
                           title=parse_page_title(html), **detail)

    title = parse_page_title(html)
    detail['title'] = title
    if title:
        ok = code in title
    else:
        ok = (f"cmp_cd: '{code}'" in html or f'cmp_cd={code}' in html
              or f'value="{code}"' in html)
    if not ok:
        raise FnGuideError(
            'wrong_stock',
            f'요청 종목({code})과 다른 페이지가 왔다. title={title!r} '
            '-- 파라미터가 무시되고 있을 수 있다',
            **detail)

    return html


def extract_init_payload(html: str) -> Dict[str, Any]:
    """`finance.init({ key: <json>, ... })` 임베드 payload 를 파싱.

    신 FnGuide 는 SPA 라 HTML <table> 이 전부 빈 템플릿이고, 실제 데이터는
    페이지 하단 init(...) 인자에 JSON 으로 박혀 있다. JS 객체(따옴표 없는 키,
    작은따옴표 문자열, `$(...)` 표현식 혼재)라 json.loads 로 통째로는 못 읽는다.
    """
    m = re.search(r'\b\w+\.init\(\s*\{', html or '')
    if not m:
        return {}

    dec = json.JSONDecoder()
    i, n = m.end(), len(html)
    out: Dict[str, Any] = {}
    key_re = re.compile(r'\s*,?\s*([A-Za-z_]\w*)\s*:\s*')

    while i < n:
        km = key_re.match(html, i)
        if not km:
            break
        key, j = km.group(1), km.end()
        if j >= n:
            break
        ch = html[j]
        if ch in '{[':
            try:
                val, i = dec.raw_decode(html, j)
            except ValueError:
                break
            out[key] = val
        elif ch in '\'"':
            q, k = ch, j + 1
            while k < n and html[k] != q:
                k += 2 if html[k] == '\\' else 1
            out[key] = html[j + 1:k]
            i = k + 1
        else:
            k, depth = j, 0
            while k < n:
                c = html[k]
                if c in '([':
                    depth += 1
                elif c in ')]':
                    depth -= 1
                elif depth <= 0 and c in ',}\n':
                    break
                k += 1
            out[key] = html[j:k].strip()
            i = k
        while i < n and html[i] in ' \t\r\n':
            i += 1
        if i < n and html[i] == ',':
            i += 1
        elif i < n and html[i] == '}':
            break
    return out


def extract_tables(html: str) -> Tuple[List[pd.DataFrame], List[int]]:
    """<table> 을 개별 추출해 하나씩 read_html. 깨진 표는 건너뛴다.

    전체 HTML 을 통째로 `pd.read_html` 하면 표 하나가 깨졌을 때 IndexError 로
    전부 죽는다 (Snapshot 9개 중 2개가 실제로 깨져 있다). 그래서 개별 파싱한다.

    Returns: (성공한 DataFrame 리스트, 실패한 표의 인덱스 리스트)
    """
    raw = re.findall(r'<table.*?</table>', html or '', re.S | re.I)
    ok: List[pd.DataFrame] = []
    broken: List[int] = []
    for idx, t in enumerate(raw):
        try:
            dfs = pd.read_html(io.StringIO(t))
            if not dfs:
                broken.append(idx)
                continue
            ok.append(dfs[0])
        except Exception:
            broken.append(idx)
    return ok, broken


def _num(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if (isinstance(v, float) and np.isnan(v)) else float(v)
    s = str(v).replace(',', '').replace('%', '').strip()
    if s in ('', '-', 'N/A', 'nan', 'None'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ============================================================================
# 저수준: dataset 파싱
# ============================================================================

def _dataset_periods(header: List[Dict], freq: str) -> List[Tuple[str, str]]:
    """dataset.header -> [(VALn 키, 'YYYY/MM')]

    FnGuide 헤더에는 비교용 컬럼이 섞여 있다:
      연간(Y): 2023/12, 2024/12, 2025/12, '2026/06 (최근분기)', '2025/06 (전년동기)', '전년동기대비(%)'
      분기(Q): 2025/09, 2025/12, 2026/03, '2026/06 (최근분기)', '2025/06 (전년동기)', '전년동기대비(%)'

    연간에서 '(최근분기)' 는 반기 누적값이므로 반드시 제외해야 한다
    (구 코드가 늘 틀리던 지점). 분기에서는 그것이 최신 분기이므로 살린다.
    """
    out = []
    for h in header or []:
        cd = h.get('CD')
        y = (h.get('YYMM') or '').strip()
        if not cd or not y:
            continue
        if '전년동기' in y or '대비' in y:
            continue
        m = re.match(r'^(\d{4}/\d{2})\s*(\([^)]*\))?$', y)
        if not m:
            continue
        period, suffix = m.group(1), m.group(2) or ''
        if freq == 'Y' and suffix:
            continue
        out.append((cd, period))
    return out


def parse_fin_dataset(dataset: Dict, item_map: Dict[str, str], freq: str) -> Dict[str, Dict[str, float]]:
    """{'header': [...], 'data': [...]} -> {영문키: {'2025/12': 값, ...}}

    계정명은 **정확 일치**로 잡는다. 신 dataset 은 LVL 2 하위 계정에 '기타',
    '이자수익' 같은 중복 이름이 많아서 부분 일치는 오매칭을 만든다.
    같은 이름이 여러 번 나오면 처음(상위 LVL) 것만 쓴다.
    """
    if not isinstance(dataset, dict):
        return {}
    periods = _dataset_periods(dataset.get('header') or [], freq)
    if not periods:
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for row in dataset.get('data') or []:
        name = (row.get('NAME') or '').strip()
        key = item_map.get(name)
        if not key or key in out:
            continue
        vals = {}
        for cd, period in periods:
            v = _num(row.get(cd))
            if v is not None:
                vals[period] = v
        if vals:
            out[key] = vals
    return out


def _parse_chart_dataset(dataset: Dict, item_map: Dict[str, str]) -> Dict[str, Dict[str, float]]:
    """getFinIncomeMajorChart 형태 ({'header':[{ID,NM}], 'data':[{TRD_DT, VAL1..}]})"""
    if not isinstance(dataset, dict):
        return {}
    id_to_key = {}
    for h in dataset.get('header') or []:
        key = item_map.get((h.get('NM') or '').strip())
        if key and h.get('ID'):
            id_to_key[h['ID']] = key
    out: Dict[str, Dict[str, float]] = {}
    for row in dataset.get('data') or []:
        period = (row.get('TRD_DT') or '').strip()
        if not re.match(r'^\d{4}/\d{2}$', period):
            continue
        for vid, key in id_to_key.items():
            v = _num(row.get(vid))
            if v is not None:
                out.setdefault(key, {})[period] = v
    return out


def _latest_balance(by_period: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """{'total_assets': {'2025/12': v, ...}} -> {'total_assets': 최신값}"""
    out = {}
    for key, series in by_period.items():
        if not series:
            continue
        latest = max(series)
        out[key] = float(series[latest])
    if out:
        out['total_debt'] = (out.get('short_term_debt') or 0) \
            + (out.get('long_term_debt') or 0) + (out.get('bonds') or 0)
    return out


def _avg_balance(by_period: Dict[str, Dict[str, float]], n: int = 4) -> Dict[str, float]:
    out = {}
    for key, series in by_period.items():
        vals = [series[p] for p in sorted(series, reverse=True)[:n]]
        if vals:
            out[key] = float(sum(vals) / len(vals))
    return out


# ============================================================================
# 페이지 파서 (네트워크 없이 테스트 가능)
# ============================================================================

def parse_finance_page(html: str, code: str, status: int = 200, url: str = '') -> Dict[str, Any]:
    """/CompanyInfo/Finance 페이지 -> 연간 손익/재무상태/현금흐름"""
    validate_page(html, code, status=status, page='finance', url=url)
    payload = extract_init_payload(html)
    if not any(k in payload for k in ('finIncome', 'finBalance', 'finCashFlow')):
        ok, broken = extract_tables(html)
        raise FnGuideError('no_payload',
                           'Finance 페이지에 finIncome/finBalance/finCashFlow 임베드 JSON 이 없다',
                           code=code, page='finance', url=url, status=status,
                           length=len(html), tables_ok=len(ok), tables_broken=len(broken))

    annual = parse_fin_dataset(payload.get('finIncome') or {}, INCOME_MAP, 'Y')
    balance_series = parse_fin_dataset(payload.get('finBalance') or {}, BALANCE_MAP, 'Y')
    cash_series = parse_fin_dataset(payload.get('finCashFlow') or {}, CASHFLOW_MAP, 'Y')

    # 차트 엔드포인트가 표보다 1년 더 길다 -> 없는 과거 연도만 보충
    chart = _parse_chart_dataset(payload.get('finIncomeMajorChart') or {}, CHART_MAP)
    for key, series in chart.items():
        tgt = annual.setdefault(key, {})
        for period, v in series.items():
            tgt.setdefault(period, v)

    cashflow = {}
    if cash_series.get('cfo'):
        cashflow['cfo_annual'] = cash_series['cfo']
    if cash_series.get('invest_cf'):
        cashflow['invest_cf_annual'] = cash_series['invest_cf']
    if cash_series.get('fin_cf'):
        cashflow['fin_cf_annual'] = cash_series['fin_cf']

    return {
        'annual': annual,
        'annual_chart': chart,
        'balance_series': balance_series,
        'balance': _latest_balance(balance_series),
        'balance_avg': _avg_balance(balance_series),
        'cashflow': cashflow,
        'consol_typ': payload.get('consol_typ'),
    }


def parse_quarter_dataset(income: Dict, balance: Dict, cashflow: Dict) -> Dict[str, Any]:
    """getFinIncome/getFinBalance/getFinCashFlow (freq_typ=Q) JSON -> 분기 데이터"""
    def ds(x):
        if isinstance(x, dict) and 'dataset' in x:
            return x['dataset']
        return x or {}

    quarter = parse_fin_dataset(ds(income), INCOME_MAP, 'Q')
    bal = parse_fin_dataset(ds(balance), BALANCE_MAP, 'Q')
    cf = parse_fin_dataset(ds(cashflow), CASHFLOW_MAP, 'Q')

    out_cf = {}
    if cf.get('cfo'):
        out_cf['cfo_quarter'] = cf['cfo']
    if cf.get('invest_cf'):
        out_cf['invest_cf_quarter'] = cf['invest_cf']
    if cf.get('fin_cf'):
        out_cf['fin_cf_quarter'] = cf['fin_cf']

    return {
        'quarter': quarter,
        'balance_series': bal,
        'balance': _latest_balance(bal),
        'balance_avg': _avg_balance(bal),
        'cashflow': out_cf,
    }


def parse_header_metrics(html: str) -> Dict[str, float]:
    """헤더 PER / 12M PER / 업종 PER / PBR / 배당수익률

    신 마크업:
        <button type="button" class="tip_in" id="h_pbr">PBR</button>
        </li>
        <li>1.80 </li>
    """
    metrics: Dict[str, float] = {}
    pattern = re.compile(
        r'id="(h_[a-z0-9_]+)"[^>]*>.*?</button>\s*</li>\s*<li[^>]*>([^<]*)</li>',
        re.S | re.I)
    for m in pattern.finditer(html or ''):
        key = HEADER_METRIC_IDS.get(m.group(1))
        if not key or key in metrics:
            continue
        v = _num(m.group(2))
        if v is not None:
            metrics[key] = v
    return metrics


def _snapshot_summary_table(tables: List[pd.DataFrame]) -> Dict[str, float]:
    """투자의견 / 목표주가 / EPS / PER / 추정기관수"""
    want = {'투자의견': 'opinion', '목표주가': 'target_price', 'EPS': 'eps',
            'PER': 'per', '추정기관수': 'n_estimates'}
    for df in tables:
        cols = [str(c).strip() for c in df.columns]
        if '목표주가' in cols and '추정기관수' in cols and len(df) >= 1:
            out = {}
            row = df.iloc[0]
            for c in cols:
                k = want.get(c)
                if k:
                    v = _num(row[c])
                    if v is not None:
                        out[k] = int(v) if k in ('target_price', 'n_estimates') else v
            if out:
                return out
    return {}


def _snapshot_price_table(tables: List[pd.DataFrame]) -> Dict[str, Any]:
    """종가 / 52주 / 시가총액 / 발행주식수 / 베타 (라벨-값 2쌍 구조)"""
    label_map = {
        '종가/ 전일대비/수익률': 'close_raw',
        '52주.최고가/ 최저가': 'week52_raw',
        '수익률(1M/ 3M/ 6M/ 1Y)': 'returns_raw',
        '시가총액  (보통주,억원)': 'market_cap',
        '시가총액  (상장예정포함,억원)': 'market_cap_incl',
        '발행주식수(보통주/ 우선주)': 'shares_raw',
        '유동주식수/비율  (보통주)': 'free_float_raw',
        '외국인지분율': 'foreign_ratio',
        '52주베타': 'beta',
        '액면가': 'par_value',
        '거래량': 'volume',
        '거래대금(억원)': 'trade_value',
    }
    numeric = {'market_cap', 'market_cap_incl', 'foreign_ratio', 'beta',
               'par_value', 'volume', 'trade_value'}
    for df in tables:
        flat = [str(x) for x in df.iloc[:, 0].tolist()]
        if not any('종가' in x for x in flat):
            continue
        out: Dict[str, Any] = {}
        arr = df.values.tolist()
        for row in arr:
            for i in range(0, len(row) - 1, 2):
                label = re.sub(r'\s+', ' ', str(row[i])).strip()
                key = None
                for raw_label, k in label_map.items():
                    if re.sub(r'\s+', ' ', raw_label).strip() == label:
                        key = k
                        break
                if not key:
                    continue
                val = row[i + 1]
                out[key] = _num(val) if key in numeric else (
                    None if val is None or str(val) == 'nan' else str(val).strip())
        if out:
            return out
    return {}


def _snapshot_annual_extra(payload: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """snpFinancial 임베드 dataset -> 연간 실측 ROE/EPS/BPS/발행주식수 등.

    header 가 [연간 3년 + 연간 추정 1년] + [분기 4개] 로 붙어 있어서 YYMM 이 중복된다.
    **단조 증가 prefix** 만 연간 블록으로 본다 (분기 블록은 과거로 되돌아간다).
    추정(EP_CHK='E') 컬럼은 실측이 아니므로 제외한다.
    """
    ds = payload.get('snpFinancial')
    if not isinstance(ds, dict):
        return {}
    header = ds.get('header') or []
    periods: List[Tuple[str, str]] = []
    prev = ''
    for h in header:
        y = (h.get('YYMM') or '').strip()
        if not re.match(r'^\d{4}/\d{2}$', y) or y <= prev:
            break
        prev = y
        if (h.get('EP_CHK') or '').strip() == 'E':
            continue
        if h.get('CD'):
            periods.append((h['CD'], y))
    if not periods:
        return {}
    out: Dict[str, Dict[str, float]] = {}
    for row in ds.get('data') or []:
        key = SNP_ANNUAL_MAP.get((row.get('NAME') or '').strip())
        if not key or key in out:
            continue
        vals = {}
        for cd, period in periods:
            v = _num(row.get(cd))
            if v is not None:
                vals[period] = v
        if vals:
            out[key] = vals
    return out


def parse_snapshot_page(html: str, code: str, status: int = 200, url: str = '') -> Dict[str, Any]:
    """/CompanyInfo/Snapshot -> 헤더 지표 + 컨센 요약 + 시세/시총 + 연간 비율"""
    validate_page(html, code, status=status, page='snapshot', url=url)
    tables, broken = extract_tables(html)
    payload = extract_init_payload(html)
    return {
        'header': parse_header_metrics(html),
        'consensus_summary': _snapshot_summary_table(tables),
        'price': _snapshot_price_table(tables),
        'annual': _snapshot_annual_extra(payload),
        'tables_ok': len(tables),
        'tables_broken': len(broken),
    }


def parse_consensus_page(html: str, code: str, status: int = 200, url: str = '') -> Dict[str, Any]:
    """/CompanyInfo/Consensus -> 3년 컨센 추정 (+ 실적 실측 3년)

    Returns:
        {'revenue': {'2026/12(E)': ...}, ..., '_meta': {'actual': {...}, ...}}
    """
    validate_page(html, code, status=status, page='consensus', url=url)
    payload = extract_init_payload(html)
    ds = payload.get('perforTrend')
    if not isinstance(ds, dict):
        raise FnGuideError('no_payload',
                           'Consensus 페이지에 perforTrend 임베드 JSON 이 없다',
                           code=code, page='consensus', url=url, status=status,
                           length=len(html))

    est_cols, act_cols = [], []
    for h in ds.get('header') or []:
        y = (h.get('YYMM') or '').strip()
        cd = h.get('CD')
        if not cd or not re.match(r'^\d{4}/\d{2}$', y):
            continue
        if (h.get('EP_CHK') or '').strip() == 'E':
            est_cols.append((cd, f'{y}(E)'))
        else:
            act_cols.append((cd, y))

    def collect(cols):
        out: Dict[str, Dict[str, float]] = {}
        for row in ds.get('data') or []:
            key = CONSENSUS_MAP.get((row.get('NAME') or '').strip())
            if not key or key in out or (row.get('LVL') or 1) > 1:
                continue
            vals = {}
            for cd, label in cols:
                v = _num(row.get(cd))
                if v is not None:
                    vals[label] = v
            if vals:
                out[key] = vals
        return out

    result = collect(est_cols)
    actual = collect(act_cols)
    if not result:
        raise FnGuideError('no_data',
                           f'Consensus 페이지에 추정(E) 컬럼이 없다 (컨센 미공시 종목일 수 있음). '
                           f'실측 컬럼 {len(act_cols)}개',
                           code=code, page='consensus', url=url, status=status,
                           length=len(html))
    result['_meta'] = {
        'source': f'{FNGUIDE_BASE}{PAGE_PATH["consensus"]}?cmp_cd={code}',
        'actual': actual,
        'estimate_periods': [lbl for _, lbl in est_cols],
        # 신 FnGuide 컨센 데이터셋에는 ROE 추정치가 없다 (구 SVD_Main 에는 있었음)
        'unavailable': ['roe'],
    }
    return result


# ============================================================================
# 조립 + TTM
# ============================================================================

CORE_CHECKS = [
    ('annual', 'revenue', '연간 매출액'),
    ('annual', 'operating_income', '연간 영업이익'),
    ('annual', 'net_income', '연간 당기순이익'),
    ('quarter', 'revenue', '분기 매출액'),
]


def assemble_financial_data(code: str, finance: Dict[str, Any],
                            snapshot: Dict[str, Any],
                            quarter: Dict[str, Any]) -> Dict[str, Any]:
    """페이지 파싱 결과 3종 -> 최종 재무 dict (+ TTM + 경고)"""
    finance = finance or {}
    snapshot = snapshot or {}
    quarter = quarter or {}

    annual = {k: dict(v) for k, v in (finance.get('annual') or {}).items()}
    for key, series in (snapshot.get('annual') or {}).items():
        tgt = annual.setdefault(key, {})
        for period, v in series.items():
            tgt.setdefault(period, v)

    cashflow = dict(finance.get('cashflow') or {})
    cashflow.update(quarter.get('cashflow') or {})

    balance = quarter.get('balance') or finance.get('balance') or {}
    balance_avg = quarter.get('balance_avg') or finance.get('balance_avg') or {}

    result: Dict[str, Any] = {
        'code': code,
        'annual': annual,
        'quarter': quarter.get('quarter') or {},
        'balance': dict(balance),
        'balance_avg': dict(balance_avg),
        'cashflow': cashflow,
        'header': snapshot.get('header') or {},
        'consensus_summary': snapshot.get('consensus_summary') or {},
        'price': snapshot.get('price') or {},
    }

    _calculate_ttm(result)

    warnings: List[str] = []
    for bucket, key, label in CORE_CHECKS:
        if not (result.get(bucket) or {}).get(key):
            warnings.append(f'{label} 데이터 없음')
    if not result['balance'].get('total_assets'):
        warnings.append('자산총계 데이터 없음')
    if not cashflow.get('cfo_annual') and not cashflow.get('cfo_quarter'):
        warnings.append('영업활동현금흐름 데이터 없음')
    if not result['header'].get('per') and not result['header'].get('pbr'):
        warnings.append('헤더 PER/PBR 지표 없음')

    n_years = len(annual.get('revenue') or {})
    result['_meta'] = {
        'source': FNGUIDE_BASE,
        'collected_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'annual_periods': sorted(annual.get('revenue') or {}),
        'quarter_periods': sorted((result['quarter'].get('revenue') or {})),
        'warnings': warnings,
        'notes': [] if n_years >= 4 else
                 [f'연간 실적 {n_years}개년만 확보 (신 FnGuide 는 최대 4개년 제공)'],
    }
    return result


def _calculate_ttm(data: Dict[str, Any]) -> None:
    """TTM = 최근 4분기 합. 분기 4개 미만이면 최신 연간값 대체."""
    for key in ['revenue', 'operating_income', 'net_income', 'gross_profit',
                'net_income_controlling', 'tax_expense', 'finance_cost']:
        annual = data['annual'].get(key, {})
        quarter = data['quarter'].get(key, {})

        ttm_value = None
        if len(quarter) >= 4:
            sorted_quarters = sorted(quarter.items(), key=lambda x: x[0], reverse=True)
            recent_4 = [v for _, v in sorted_quarters[:4] if v is not None and not np.isnan(v)]
            if len(recent_4) == 4:
                ttm_value = sum(recent_4)

        if ttm_value is None and annual:
            for _, v in sorted(annual.items(), key=lambda x: x[0], reverse=True):
                if v is not None and not np.isnan(v):
                    ttm_value = v
                    break

        if ttm_value is not None:
            data[f'{key}_ttm'] = ttm_value

    for out_key, a_key, q_key in [('cfo_ttm', 'cfo_annual', 'cfo_quarter'),
                                  ('invest_cf_ttm', 'invest_cf_annual', 'invest_cf_quarter')]:
        a = data['cashflow'].get(a_key, {})
        q = data['cashflow'].get(q_key, {})
        val = None
        if len(q) >= 4:
            recent_4 = [v for _, v in sorted(q.items(), key=lambda x: x[0], reverse=True)[:4]
                        if v is not None and not np.isnan(v)]
            if len(recent_4) == 4:
                val = sum(recent_4)
        if val is None and a:
            for _, v in sorted(a.items(), key=lambda x: x[0], reverse=True):
                if v is not None and not np.isnan(v):
                    val = v
                    break
        if val is not None:
            data[out_key] = val


# ============================================================================
# 메인 수집 함수
# ============================================================================

def _fetch_page(code: str, page: str, fetch=None, timeout: int = DEFAULT_TIMEOUT) -> str:
    fetch = fetch or _http_get
    url = FNGUIDE_BASE + PAGE_PATH[page]
    params = {'c_id': 'AA', 'menu_type': '01', 'cmp_cd': code}
    status, html = fetch(url, params, timeout)
    return validate_page(html, code, status=status, page=page, url=url)


def _fetch_json(code: str, endpoint: str, params: Dict[str, str],
                fetch=None, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    fetch = fetch or _http_get
    url = AJAX_BASE + endpoint
    q = dict(params)
    q['cmp_cd'] = code
    status, text = fetch(url, q, timeout)
    if status != 200:
        raise FnGuideError('http_status', f'HTTP {status}', code=code,
                           endpoint=endpoint, url=url, status=status, length=len(text or ''))
    for marker in ERROR_MARKERS:
        if marker in (text or ''):
            raise FnGuideError('error_page', f'에러 페이지 응답 (marker={marker!r})',
                               code=code, endpoint=endpoint, url=url,
                               status=status, length=len(text or ''))
    try:
        payload = json.loads(text)
    except (ValueError, TypeError) as e:
        raise FnGuideError('bad_json', f'JSON 파싱 실패: {e}', code=code,
                           endpoint=endpoint, url=url, status=status,
                           length=len(text or ''))
    ds = payload.get('dataset') if isinstance(payload, dict) else None
    if not isinstance(ds, dict) or not ds.get('data'):
        raise FnGuideError('no_data', f'{endpoint} 응답에 dataset.data 가 없다',
                           code=code, endpoint=endpoint, url=url,
                           status=status, length=len(text or ''))
    return ds


def get_financial_data(code: str, retry: int = 2, fetch=None,
                       _fetch=None) -> Optional[Dict[str, Any]]:
    """FnGuide 재무데이터 수집.

    성공: dict (annual / quarter / balance / balance_avg / cashflow / header /
                *_ttm / consensus_summary / price / _meta)
    실패: None -- 단, **왜 실패했는지를 stderr 에 출력하고 LAST_ERRORS 에 남긴다.**
          FNGUIDE_STRICT=1 이면 FnGuideError 를 그대로 던진다.

    Args:
        fetch/_fetch: 테스트 주입용 `(url, params, timeout) -> (status, text)`
    """
    fetch = fetch or _fetch
    last_err: Optional[FnGuideError] = None

    for attempt in range(max(1, retry)):
        try:
            with ThreadPoolExecutor(max_workers=5) as ex:
                f_fin = ex.submit(_fetch_page, code, 'finance', fetch)
                f_snp = ex.submit(_fetch_page, code, 'snapshot', fetch)
                qp = {'freq_typ': 'Q', 'consol_typ': 'C'}
                f_qi = ex.submit(_fetch_json, code, 'getFinIncome', qp, fetch)
                f_qb = ex.submit(_fetch_json, code, 'getFinBalance', qp, fetch)
                f_qc = ex.submit(_fetch_json, code, 'getFinCashFlow', qp, fetch)

                fin_html = f_fin.result()
                # Snapshot / 분기는 실패해도 치명적이지 않다 -- 경고로 낮춘다
                snap_html, q_income, q_balance, q_cash = None, {}, {}, {}
                for fut, name, setter in [
                    (f_snp, 'snapshot', 'snap'),
                    (f_qi, 'getFinIncome(Q)', 'qi'),
                    (f_qb, 'getFinBalance(Q)', 'qb'),
                    (f_qc, 'getFinCashFlow(Q)', 'qc'),
                ]:
                    try:
                        val = fut.result()
                    except FnGuideError as e:
                        _record_warning(f'{code} {name} 수집 실패 -- {e}')
                        continue
                    if setter == 'snap':
                        snap_html = val
                    elif setter == 'qi':
                        q_income = val
                    elif setter == 'qb':
                        q_balance = val
                    else:
                        q_cash = val

            finance = parse_finance_page(fin_html, code)
            snapshot = (parse_snapshot_page(snap_html, code) if snap_html else
                        {'header': {}, 'consensus_summary': {}, 'price': {}, 'annual': {}})
            quarter = parse_quarter_dataset(q_income, q_balance, q_cash)

            data = assemble_financial_data(code, finance, snapshot, quarter)
            for w in data['_meta']['warnings']:
                _record_warning(f'{code}: {w}')
            return data

        except FnGuideError as e:
            last_err = e
            if attempt < retry - 1:
                time.sleep(0.5)
        except Exception as e:  # 예상 못 한 실패도 삼키지 않는다
            last_err = FnGuideError('unexpected', f'{type(e).__name__}: {e}', code=code)
            if attempt < retry - 1:
                time.sleep(0.5)

    if last_err is not None:
        _record_error(last_err)
        if _strict():
            raise last_err
    return None


def get_consensus_estimates(code: str, retry: int = 2, fetch=None,
                            _fetch=None) -> Dict[str, Dict[str, float]]:
    """FnGuide 컨센서스 3년 추정. 실패 시 {} + stderr 진단 + LAST_ERRORS 기록.

    [주의] ROE 추정치는 신 FnGuide 컨센 데이터셋에 없다 (`_meta['unavailable']`).
    """
    fetch = fetch or _fetch
    last_err: Optional[FnGuideError] = None
    for attempt in range(max(1, retry)):
        try:
            html = _fetch_page(code, 'consensus', fetch)
            return parse_consensus_page(html, code)
        except FnGuideError as e:
            last_err = e
            if attempt < retry - 1:
                time.sleep(0.5)
        except Exception as e:
            last_err = FnGuideError('unexpected', f'{type(e).__name__}: {e}', code=code)
            if attempt < retry - 1:
                time.sleep(0.5)

    if last_err is not None:
        _record_error(last_err)
        if _strict():
            raise last_err
    return {}


# ============================================================================
# 배치 수집
# ============================================================================

def get_financial_data_batch(codes: List[str], delay: float = 0.3) -> Dict[str, Dict]:
    """여러 종목 순차 수집. 실패 종목은 stderr 에 사유가 남는다."""
    results = {}
    failed = []
    total = len(codes)

    print(f"FnGuide 재무데이터 수집 시작 ({total}개 종목)", file=sys.stderr)

    for i, code in enumerate(codes):
        data = get_financial_data(code)
        if data:
            results[code] = data
        else:
            failed.append(code)

        if (i + 1) % 50 == 0 or (i + 1) == total:
            print(f"  진행: {i + 1}/{total} (수집: {len(results)}개, 실패: {len(failed)}개)",
                  file=sys.stderr)

        if delay > 0:
            time.sleep(delay)

    print(f"수집 완료: {len(results)}/{total}개", file=sys.stderr)
    if failed:
        print(f"[FNGUIDE][ERROR] 실패 종목 {len(failed)}개: {failed[:20]}", file=sys.stderr)
    return results


# ============================================================================
# 헬퍼 함수 (스크리너 / 리포트 파이프라인에서 사용)
# ============================================================================

def get_ebit(data: Dict) -> Optional[float]:
    """EBIT = 영업이익 (Operating Income, TTM)"""
    op = data.get('operating_income_ttm')
    if op is not None:
        return op

    ni = data.get('net_income_ttm')
    tax = data.get('tax_expense_ttm')
    fin_cost = data.get('finance_cost_ttm')

    if ni is not None and tax is not None and fin_cost is not None:
        return ni + tax + fin_cost

    return None


def get_invested_capital(data: Dict) -> Optional[float]:
    """투하자본 = 유동자산 - 유동부채 + 비유동자산 (4분기 평균)"""
    bs = data.get('balance_avg') or data.get('balance', {})
    ca = bs.get('current_assets')
    cl = bs.get('current_liabilities')
    nca = bs.get('non_current_assets')

    if ca is not None and cl is not None and nca is not None:
        return ca - cl + nca
    return None


def get_ev(market_cap: float, data: Dict) -> Optional[float]:
    """EV = 시가총액 + 총부채 - 여유자금"""
    bs = data.get('balance', {})
    cl = bs.get('current_liabilities', 0) or 0
    ncl = bs.get('non_current_liabilities', 0) or 0
    total_liabilities = cl + ncl

    cash = bs.get('cash', 0) or 0
    ca = bs.get('current_assets', 0) or 0
    if cash > 0:
        working_capital_need = max(0, cl - ca + cash)
        excess_cash = cash - working_capital_need
    else:
        excess_cash = 0

    ev = market_cap + total_liabilities - excess_cash
    return ev if ev > 0 else market_cap


def get_roe(data: Dict) -> Optional[float]:
    """ROE = 지배주주순이익(TTM) / 지배주주지분(4분기 평균)"""
    ni = data.get('net_income_controlling_ttm') or data.get('net_income_ttm')
    bs = data.get('balance_avg') or data.get('balance', {})
    eq = bs.get('controlling_equity') or bs.get('total_equity')

    if ni is not None and eq is not None and eq > 0:
        return (ni / eq) * 100
    return None


def get_gpa(data: Dict) -> Optional[float]:
    """GPA = 매출총이익(TTM) / 총자산(4분기 평균)"""
    gp = data.get('gross_profit_ttm')
    bs = data.get('balance_avg') or data.get('balance', {})
    ta = bs.get('total_assets')

    if gp is not None and ta is not None and ta > 0:
        return gp / ta
    return None


def get_cfo_ratio(data: Dict) -> Optional[float]:
    """CFO = 영업활동현금흐름(TTM) / 총자산(4분기 평균)"""
    cfo = data.get('cfo_ttm')
    bs = data.get('balance_avg') or data.get('balance', {})
    ta = bs.get('total_assets')

    if cfo is not None and ta is not None and ta > 0:
        return cfo / ta
    return None


def get_psr(market_cap: float, data: Dict) -> Optional[float]:
    """PSR = 시가총액 / 매출액(TTM)"""
    rev = data.get('revenue_ttm')
    if rev is not None and rev > 0:
        return market_cap / rev
    return None


def get_pcr(market_cap: float, data: Dict) -> Optional[float]:
    """PCR = 시가총액 / 영업현금흐름(TTM)"""
    cfo = data.get('cfo_ttm')
    if cfo is not None and cfo > 0:
        return market_cap / cfo
    return None


def get_current_ratio(data: Dict) -> Optional[float]:
    """유동비율 = 유동자산 / 유동부채 (배수)"""
    bs = data.get('balance', {})
    ca = bs.get('current_assets')
    cl = bs.get('current_liabilities')
    if ca is not None and cl is not None and cl > 0:
        return ca / cl
    return None


def get_debt_ratio(data: Dict) -> Optional[float]:
    """부채비율 = (유동부채+비유동부채) / 자본총계 × 100"""
    bs = data.get('balance', {})
    cl = bs.get('current_liabilities', 0) or 0
    ncl = bs.get('non_current_liabilities', 0) or 0
    eq = bs.get('total_equity')
    if eq is not None and eq > 0:
        return ((cl + ncl) / eq) * 100
    return None


def get_long_term_debt_ratio(data: Dict) -> Optional[float]:
    """장기부채비율 = (장기차입금+사채) / 자본총계 × 100"""
    bs = data.get('balance', {})
    long_debt = bs.get('long_term_debt', 0) or 0
    bonds = bs.get('bonds', 0) or 0
    eq = bs.get('total_equity')
    if eq is not None and eq > 0 and (long_debt + bonds) > 0:
        return ((long_debt + bonds) / eq) * 100
    return None


def get_roa(data: Dict) -> Optional[float]:
    """ROA = 순이익(TTM) / 총자산(4분기 평균) × 100"""
    ni = data.get('net_income_ttm')
    bs = data.get('balance_avg') or data.get('balance', {})
    ta = bs.get('total_assets')
    if ni is not None and ta is not None and ta > 0:
        return (ni / ta) * 100
    return None


def get_roic(data: Dict) -> Optional[float]:
    """ROIC = EBIT / 투하자본 × 100"""
    ebit = get_ebit(data)
    ic = get_invested_capital(data)
    if ebit is not None and ic is not None and ic > 0:
        return (ebit / ic) * 100
    return None


def get_net_current_assets(data: Dict) -> Optional[float]:
    """순유동자산 = 유동자산 - 유동부채 (억원)"""
    bs = data.get('balance', {})
    ca = bs.get('current_assets')
    cl = bs.get('current_liabilities')
    if ca is not None and cl is not None:
        return ca - cl
    return None


def get_fcf(data: Dict) -> Optional[float]:
    """FCF = CFO(TTM) + 투자활동CF(TTM)  (투자CF는 음수이므로 + 연산)"""
    cfo = data.get('cfo_ttm')
    inv_cf = data.get('invest_cf_ttm')
    if cfo is not None and inv_cf is not None:
        return cfo + inv_cf
    return None


def get_inventory_ratio(data: Dict) -> Optional[float]:
    """재고/매출 비율 = 재고자산(4Q평균) / 매출액(TTM) × 100"""
    bs = data.get('balance_avg') or data.get('balance', {})
    inv = bs.get('inventory')
    rev = data.get('revenue_ttm')
    if inv is not None and rev is not None and rev > 0:
        return (inv / rev) * 100
    return None


def get_peg(market_cap: float, data: Dict) -> Optional[float]:
    """PEG = PER / EPS성장률(3년평균). 성장률이 음수면 None."""
    per = get_per_from_data(market_cap, data)
    if per is None or per <= 0:
        return None

    growth_rates = get_annual_growth_rates(data, 'eps', years=3)
    if not growth_rates:
        growth_rates = get_growth_rates_with_ttm(data, 'net_income', years=3)
    valid_rates = [r for r in growth_rates if r is not None and r > 0]
    if not valid_rates:
        return None

    avg_growth = sum(valid_rates) / len(valid_rates)
    if avg_growth <= 0:
        return None

    return per / avg_growth


# ============================================================================
# 캐시 저장/로드
# ============================================================================

def save_fnguide_cache(results: Dict[str, Dict], filepath: str) -> None:
    """FnGuide 수집 결과를 pickle 캐시로 저장"""
    import pickle
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'wb') as f:
        pickle.dump(results, f, protocol=pickle.HIGHEST_PROTOCOL)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"캐시 저장: {filepath} ({len(results)}개 종목, {size_mb:.1f}MB)", file=sys.stderr)


def load_fnguide_cache(filepath: str = None) -> Optional[Dict[str, Dict]]:
    """FnGuide pickle 캐시 로드. filepath 이 None 이면 .cache/ 최신 파일 탐색."""
    import pickle
    import glob as glob_mod

    if filepath and os.path.exists(filepath):
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            print(f"캐시 로드: {filepath} ({len(data)}개 종목)", file=sys.stderr)
            return data
        except Exception as e:
            print(f"캐시 로드 실패: {e}", file=sys.stderr)
            return None

    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_dir = os.path.join(script_dir, '.cache')
    if not os.path.exists(cache_dir):
        return None

    pkl_files = sorted(glob_mod.glob(os.path.join(cache_dir, 'fnguide_*.pkl')), reverse=True)
    for pkl_file in pkl_files:
        try:
            with open(pkl_file, 'rb') as f:
                data = pickle.load(f)
            print(f"캐시 로드: {pkl_file} ({len(data)}개 종목)", file=sys.stderr)
            return data
        except Exception:
            continue

    return None


# ============================================================================
# 성장률/마진 헬퍼
# ============================================================================

def get_growth_rates_with_ttm(data: Dict, key: str, years: int = 5) -> List[Optional[float]]:
    """TTM 값 + 연간 데이터로 YoY 성장률 시리즈 구성."""
    ttm = data.get(f'{key}_ttm')
    annual = data.get('annual', {}).get(key, {})

    sorted_annual = sorted(annual.items(), key=lambda x: x[0], reverse=True)
    annual_values = [v for _, v in sorted_annual]

    values = ([ttm] + annual_values) if ttm is not None else annual_values

    rates = []
    for i in range(min(years, len(values) - 1)):
        curr, prev = values[i], values[i + 1]
        if curr is not None and prev is not None and prev != 0 and not np.isnan(curr) and not np.isnan(prev):
            rates.append(round(((curr / prev) - 1) * 100, 2))
        else:
            rates.append(None)

    return rates


def get_annual_growth_rates(data: Dict, key: str, years: int = 5) -> List[Optional[float]]:
    """연간 데이터만으로 YoY 성장률 계산 (TTM 미포함)."""
    annual = data.get('annual', {}).get(key, {})
    sorted_annual = sorted(annual.items(), key=lambda x: x[0], reverse=True)
    values = [v for _, v in sorted_annual]

    rates = []
    for i in range(min(years, len(values) - 1)):
        curr, prev = values[i], values[i + 1]
        if curr is not None and prev is not None and prev != 0 and not np.isnan(curr) and not np.isnan(prev):
            rates.append(round(((curr / prev) - 1) * 100, 2))
        else:
            rates.append(None)

    return rates


def get_operating_margins(data: Dict, years: int = 5) -> List[Optional[float]]:
    """영업이익률 시리즈 반환 (TTM + 연간)."""
    margins = []

    rev_ttm = data.get('revenue_ttm')
    op_ttm = data.get('operating_income_ttm')
    if rev_ttm and op_ttm and rev_ttm != 0:
        margins.append(round((op_ttm / rev_ttm) * 100, 2))

    annual_rev = data.get('annual', {}).get('revenue', {})
    annual_op = data.get('annual', {}).get('operating_income', {})

    sorted_years = sorted(annual_rev.keys(), reverse=True)
    for year in sorted_years[:years]:
        rev = annual_rev.get(year)
        op = annual_op.get(year)
        if rev and op and rev != 0:
            margins.append(round((op / rev) * 100, 2))
        else:
            margins.append(None)

    return margins[:years + 1]


def get_per_from_data(market_cap: float, data: Dict) -> Optional[float]:
    """PER: FnGuide 헤더값 우선, 없으면 시가총액/순이익TTM으로 계산"""
    header_per = data.get('header', {}).get('per')
    if header_per is not None and header_per > 0:
        return round(header_per, 2)
    ni = data.get('net_income_controlling_ttm') or data.get('net_income_ttm')
    if ni is not None and ni > 0 and market_cap > 0:
        return round(market_cap / ni, 2)
    return None


def get_pbr_from_data(market_cap: float, data: Dict) -> Optional[float]:
    """PBR: FnGuide 헤더값 우선, 없으면 시가총액/자본총계로 계산"""
    header_pbr = data.get('header', {}).get('pbr')
    if header_pbr is not None and header_pbr > 0:
        return round(header_pbr, 2)
    bs = data.get('balance', {})
    eq = bs.get('controlling_equity') or bs.get('total_equity')
    if eq is not None and eq > 0 and market_cap > 0:
        return round(market_cap / eq, 2)
    return None


# ============================================================================
# CLI
# ============================================================================

def _cli(argv: List[str]) -> int:
    """stdout = JSON (research.md 가 `> data/{종목}/_fnguide.json` 로 받는다)
       stderr = 진단.  실패 시 exit code 1 -- 파이프라인이 조용히 넘어가지 못하게."""
    code = None
    for a in argv[1:]:
        if re.fullmatch(r'\d{6}', a):
            code = a
            break
    if not code:
        print('사용법: python scripts/fnguide_data.py {6자리 종목코드}', file=sys.stderr)
        return 2

    data = get_financial_data(code)
    est = get_consensus_estimates(code)

    out = {'financial': data, 'consensus_estimates': est}
    sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    sys.stdout.write('\n')

    if data is None:
        print(f'[FNGUIDE][ERROR] {code} 재무 수집 실패 -- financial=null 로 저장됐다. '
              f'위 진단을 확인하라.', file=sys.stderr)
        return 1
    if not est:
        print(f'[FNGUIDE][WARN] {code} 컨센 추정 없음 (미공시 종목이거나 수집 실패)',
              file=sys.stderr)
    warns = (data.get('_meta') or {}).get('warnings') or []
    if warns:
        print(f'[FNGUIDE][WARN] {code} 결측 필드: {warns}', file=sys.stderr)
    # 매출이 비면 리포트를 쓸 수 없다 -- 파이프라인이 조용히 넘어가지 못하게 exit 1
    if not (data.get('annual') or {}).get('revenue'):
        print(f'[FNGUIDE][ERROR] {code} 연간 매출액이 비었다 -- 사용 불가', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    sys.exit(_cli(sys.argv))
