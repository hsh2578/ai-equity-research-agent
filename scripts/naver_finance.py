"""
네이버 증권(Wisereport) 전체 파서 — v2.

네이버 증권의 "기업정보" 페이지는 Wisereport iframe.
KIS API가 주지 않는 데이터 전체를 Wisereport AJAX로 수집한다:

[finsum_more 페이지 — 정적 HTML]
- 26개 증권사별 목표주가 (컨센서스 델타 자동화)
- Forward EPS/PER/PBR/EV-EBITDA (2026E)
- 주주 구성
- 신용등급 (KIS/KR/NICE)

[cF3002.aspx AJAX — 재무제표 상세]
- rpt=1: 재무상태표 251개 세부 항목
  → 매출채권, 재고자산, 매입채무, 유형자산, 무형자산
  → CAPEX, 순부채, 순이자발생부채
- rpt=2: 현금흐름표 312개 세부 항목
  → 영업CF, 투자CF, 재무CF
  → 유형자산감가상각비, 무형자산상각비, 법인세 지급, 배당금 지급
  → 유형자산의취득 (실제 CAPEX 확인)

[cF4002.aspx AJAX — 재무비율 5종]
- rpt=1: 수익성 (ROE, ROA, ROIC, NOPLAT, IC)
- rpt=2: 성장성 (매출/영업이익/순이익/자본/자산 증가율)
- rpt=3: 안정성 (부채비율, 유동비율, 이자보상배율, 차입금의존도)
- rpt=4: 활동성 (재고/매출채권/매입채무 회전율)
- rpt=5: 가치평가 (EPS, BPS, PER, PBR, PSR, EV/EBITDA, DPS)

모든 데이터는 5년 연간 (DATA1~5) + 1년 컨센서스 (DATA6)
+ 4분기 (DATAQ1~Q5).

용도: financial_summary.json의 BS/CF/비율 주 소스.
리스크: 비공식 크롤링. 차단 시 빈 dict 반환.
"""

import io
import re
import requests
import pandas as pd
from typing import Dict, List, Optional

NAVER_WISEREPORT_URL = "https://navercomp.wisereport.co.kr/v2/company/c1010001.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
}


def _fetch_tables(code: str, timeout: int = 15):
    """Wisereport finsum_more 페이지에서 모든 테이블 반환."""
    params = {"cmp_cd": code, "target": "finsum_more"}
    try:
        resp = requests.get(NAVER_WISEREPORT_URL, params=params, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text), encoding="utf-8", displayed_only=False)
        return tables
    except Exception:
        return None


def _to_float(v, default=None):
    if v is None:
        return default
    try:
        s = str(v).replace(",", "").replace("원", "").replace("%", "").replace("억원", "").strip()
        if s.lower() == "nan":
            return default
        f = float(s)
        if f != f:  # NaN check
            return default
        return f
    except (ValueError, TypeError):
        return default


def _to_int(v, default=None):
    f = _to_float(v, default)
    if f is None:
        return default
    try:
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


def get_consensus(code: str) -> Dict:
    """증권사 컨센서스 요약 + 개별 증권사 목표주가 목록.

    Returns:
        {
            'summary': {
                'broker_count': 4,               # 추정기관 수
                'avg_target_price': 211346,      # 평균 목표주가
                'avg_eps_forward': 21747,        # 평균 Forward EPS
                'avg_per_forward': 6.92,         # 평균 Forward PER
                'consensus_score': 26,           # 컨센서스 점수 (낮을수록 Strong Buy)
            },
            'brokers': [
                {'broker': '한국투자', 'date': '26/04/09', 'target_price': 220000,
                 'prev_target': 260000, 'change_pct': -15.38, 'rating': '매수'},
                ...
            ]
        }
        실패 시 {}.
    """
    tables = _fetch_tables(code)
    if not tables or len(tables) < 13:
        return {}

    result: Dict = {}

    # Table 11: 컨센서스 요약
    try:
        t = tables[11]
        if len(t) >= 2:
            row = t.iloc[1]
            result["summary"] = {
                "broker_count": _to_int(row.iloc[1]),
                "avg_target_price": _to_int(row.iloc[2]),
                "avg_eps_forward": _to_int(row.iloc[3]),
                "avg_per_forward": _to_float(row.iloc[4]),
                "consensus_score": _to_int(row.iloc[5]),
            }
    except Exception:
        pass

    # Table 12: 증권사별 목표가
    try:
        t = tables[12]
        brokers: List[Dict] = []
        # 첫 행은 헤더
        for idx in range(len(t)):
            row = t.iloc[idx]
            broker = str(row.iloc[0]).strip() if row.iloc[0] else ""
            if not broker or broker in ("제공처", "nan"):
                continue
            brokers.append({
                "broker": broker,
                "date": str(row.iloc[1]).strip(),
                "target_price": _to_int(row.iloc[2]),
                "prev_target": _to_int(row.iloc[3]),
                "change_pct": _to_float(row.iloc[4]),
                "rating": str(row.iloc[5]).strip() if len(row) > 5 else "",
            })
        # 유효 데이터만
        result["brokers"] = [b for b in brokers if b["target_price"]]
    except Exception:
        pass

    return result


def get_forward_indicators(code: str) -> Dict:
    """Wisereport 주요지표 테이블에서 2025 Actual + 2026 Estimate 값 추출.

    Returns:
        {
            'year_actual': '2025/12',
            'year_estimate': '2026/12',
            'per_actual': 7.88,
            'per_forward': 6.92,
            'pbr_actual': 0.96,
            'pbr_forward': 0.88,
            'pcr_actual': 6.58,
            'pcr_forward': 5.15,
            'ev_ebitda_actual': 3.35,
            'ev_ebitda_forward': 2.87,
            'eps_actual': 19111,
            'eps_forward': 21747,
            'bps_actual': 157456,
            'bps_forward': 171691,
            'ebitda_actual_억': 117921,
            'ebitda_forward_억': 131900,
            'dps_actual': 6800,
            'dps_forward': 6777,
            'dividend_yield_actual': 4.52,
            'dividend_yield_forward': 4.50,
        }
    """
    tables = _fetch_tables(code)
    if not tables or len(tables) < 6:
        return {}

    try:
        t = tables[5]
        if len(t.columns) < 3:
            return {}
        result = {}
        # 컬럼명 예: ['주요지표', '2025/12(A)', '2026/12(E)']
        result["year_actual"] = str(t.columns[1]).replace("(A)", "").strip()
        result["year_estimate"] = str(t.columns[2]).replace("(E)", "").strip()
        # 행별 매핑
        row_map = {
            "PER": ("per_actual", "per_forward"),
            "PBR": ("pbr_actual", "pbr_forward"),
            "PCR": ("pcr_actual", "pcr_forward"),
            "EV/EBITDA": ("ev_ebitda_actual", "ev_ebitda_forward"),
            "EPS": ("eps_actual", "eps_forward"),
            "BPS": ("bps_actual", "bps_forward"),
            "EBITDA": ("ebitda_actual", "ebitda_forward"),
            "현금DPS": ("dps_actual", "dps_forward"),
            "현금배당수익률": ("dividend_yield_actual", "dividend_yield_forward"),
        }
        for _, row in t.iterrows():
            label = str(row.iloc[0]).strip()
            if label not in row_map:
                continue
            keys = row_map[label]
            val_a = _to_float(row.iloc[1])
            val_e = _to_float(row.iloc[2])
            if val_a is not None:
                result[keys[0]] = val_a
            if val_e is not None:
                result[keys[1]] = val_e
        return result
    except Exception:
        return {}


def get_shareholders(code: str) -> List[Dict]:
    """주주 구성.

    Returns:
        [
            {'name': '현대자동차 외 4인', 'shares': 144408540, 'pct': 36.99},
            {'name': '국민연금공단', 'shares': 26419934, 'pct': 6.77},
            ...
        ]
    """
    tables = _fetch_tables(code)
    if not tables or len(tables) < 5:
        return []

    try:
        t = tables[4]
        result = []
        for _, row in t.iterrows():
            name = str(row.iloc[0]).strip()
            shares = _to_int(row.iloc[1])
            pct = _to_float(row.iloc[2])
            if name and pct:
                result.append({"name": name, "shares": shares, "pct": pct})
        return result
    except Exception:
        return []


def get_credit_ratings(code: str) -> List[Dict]:
    """신용등급 (KIS/KR/NICE 등).

    Returns:
        [
            {'agency': 'KIS', 'bond': 'AAA', 'date': '20250602', 'cp': None},
            ...
        ]
    """
    tables = _fetch_tables(code)
    if not tables or len(tables) < 3:
        return []

    try:
        t = tables[2]
        result = []
        for _, row in t.iterrows():
            agency = str(row.iloc[0]).strip()
            bond_raw = str(row.iloc[1]).strip()
            # "AAA [20250602]" 형식
            m = re.match(r"(\S+)\s*\[(\d+)\]", bond_raw)
            if m and agency:
                result.append({
                    "agency": agency,
                    "bond": m.group(1),
                    "date": m.group(2),
                    "cp": str(row.iloc[2]).strip() if len(row) > 2 and row.iloc[2] else None,
                })
        return result
    except Exception:
        return []


def get_all_naver_data(code: str) -> Dict:
    """네이버 증권(Wisereport) 4종 데이터를 한 번에 수집.

    Returns:
        {
            'consensus': {...},
            'forward': {...},
            'shareholders': [...],
            'credit_ratings': [...],
        }
    """
    # 한 번의 요청으로 모든 테이블 파싱 (중복 호출 방지)
    tables = _fetch_tables(code)
    if not tables:
        return {}

    result = {"consensus": {}, "forward": {}, "shareholders": [], "credit_ratings": []}

    # 컨센서스 (table 11, 12)
    if len(tables) >= 13:
        try:
            t11 = tables[11]
            if len(t11) >= 2:
                row = t11.iloc[1]
                result["consensus"]["summary"] = {
                    "broker_count": _to_int(row.iloc[1]),
                    "avg_target_price": _to_int(row.iloc[2]),
                    "avg_eps_forward": _to_int(row.iloc[3]),
                    "avg_per_forward": _to_float(row.iloc[4]),
                    "consensus_score": _to_int(row.iloc[5]),
                }
            t12 = tables[12]
            brokers = []
            for idx in range(len(t12)):
                row = t12.iloc[idx]
                broker = str(row.iloc[0]).strip() if row.iloc[0] else ""
                if not broker or broker in ("제공처", "nan"):
                    continue
                tgt = _to_int(row.iloc[2])
                if tgt:
                    brokers.append({
                        "broker": broker,
                        "date": str(row.iloc[1]).strip(),
                        "target_price": tgt,
                        "prev_target": _to_int(row.iloc[3]),
                        "change_pct": _to_float(row.iloc[4]),
                        "rating": str(row.iloc[5]).strip() if len(row) > 5 else "",
                    })
            result["consensus"]["brokers"] = brokers
        except Exception:
            pass

    # Forward (table 5)
    if len(tables) >= 6:
        try:
            t = tables[5]
            fw = {}
            fw["year_actual"] = str(t.columns[1]).replace("(A)", "").strip()
            fw["year_estimate"] = str(t.columns[2]).replace("(E)", "").strip()
            row_map = {
                "PER": ("per_actual", "per_forward"),
                "PBR": ("pbr_actual", "pbr_forward"),
                "PCR": ("pcr_actual", "pcr_forward"),
                "EV/EBITDA": ("ev_ebitda_actual", "ev_ebitda_forward"),
                "EPS": ("eps_actual", "eps_forward"),
                "BPS": ("bps_actual", "bps_forward"),
                "EBITDA": ("ebitda_actual_억", "ebitda_forward_억"),
                "현금DPS": ("dps_actual", "dps_forward"),
                "현금배당수익률": ("dividend_yield_actual", "dividend_yield_forward"),
            }
            for _, row in t.iterrows():
                label = str(row.iloc[0]).strip()
                if label not in row_map:
                    continue
                keys = row_map[label]
                va = _to_float(row.iloc[1])
                ve = _to_float(row.iloc[2])
                if va is not None:
                    fw[keys[0]] = va
                if ve is not None:
                    fw[keys[1]] = ve
            result["forward"] = fw
        except Exception:
            pass

    # 주주 (table 4)
    if len(tables) >= 5:
        try:
            t = tables[4]
            sh = []
            for _, row in t.iterrows():
                name = str(row.iloc[0]).strip()
                shares = _to_int(row.iloc[1])
                pct = _to_float(row.iloc[2])
                if name and pct and name not in ("nan", "주요주주"):
                    sh.append({"name": name, "shares": shares, "pct": pct})
            result["shareholders"] = sh
        except Exception:
            pass

    # 신용등급 (table 2)
    if len(tables) >= 3:
        try:
            t = tables[2]
            cr = []
            for _, row in t.iterrows():
                agency = str(row.iloc[0]).strip()
                bond_raw = str(row.iloc[1]).strip()
                m = re.match(r"(\S+)\s*\[(\d+)\]", bond_raw)
                if m and agency and agency not in ("nan", "신용등급"):
                    cr.append({
                        "agency": agency,
                        "bond": m.group(1),
                        "date": m.group(2),
                    })
            result["credit_ratings"] = cr
        except Exception:
            pass

    return result


# ============================================================
# Wisereport AJAX 재무제표/비율 (cF3002, cF4002)
# ============================================================

WISEREPORT_BASE = "https://navercomp.wisereport.co.kr/v2/company"


def _get_encparam(page_code: str, cmp_cd: str, timeout: int = 10) -> str:
    """Wisereport 페이지에서 encparam 추출.

    encparam은 세션/페이지마다 다르므로 호출 전 동적 추출 필수.
    """
    url = f"{WISEREPORT_BASE}/{page_code}.aspx"
    try:
        resp = requests.get(url, params={"cmp_cd": cmp_cd}, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        m = re.search(r"encparam:\s*['\"]([^'\"]+)['\"]", resp.text)
        return m.group(1) if m else ""
    except Exception:
        return ""


def _fetch_cf_ajax(endpoint: str, cmp_cd: str, rpt: int, encparam: str,
                   fin_gubun: str = "MAIN1", frq: str = "0",
                   referer_page: str = "c1030001", timeout: int = 10) -> Optional[dict]:
    """Wisereport cF*.aspx AJAX 호출."""
    url = f"{WISEREPORT_BASE}/{endpoint}.aspx"
    ajax_headers = {
        **HEADERS,
        "Referer": f"{WISEREPORT_BASE}/{referer_page}.aspx?cmp_cd={cmp_cd}",
        "X-Requested-With": "XMLHttpRequest",
    }
    params = {
        "cmp_cd": cmp_cd,
        "frq": frq,
        "rpt": rpt,
        "finGubun": fin_gubun,
        "frqTyp": "0",
        "cn": "",
        "encparam": encparam,
    }
    try:
        resp = requests.get(url, params=params, headers=ajax_headers, timeout=timeout)
        if len(resp.text) < 50:
            return None
        return resp.json()
    except Exception:
        return None


def _normalize_acc_nm(name: str, skip_prev: bool = True) -> Optional[str]:
    """ACC_NM 정규화:
    - 선두의 ".", "*", 공백 제거 (Wisereport 계층 들여쓰기)
    - "<당기>", "〈전기〉" 등 꺾쇠 블록 제거 (위치 무관)
    - 내부 공백 압축

    Args:
        skip_prev: True면 "〈전기〉"/"<전기>"(previous year) 항목은 None 반환 (무시)
    """
    if not name:
        return None
    s = str(name).strip()
    # 전기(이전연도) 항목은 당기와 중복되므로 제외
    if skip_prev and re.search(r"[<〈]전기[>〉]", s):
        return None
    # 선두의 ".", "*", 공백 반복 제거
    s = re.sub(r"^[\.\*\s]+", "", s)
    # "<당기>" "<전기>" "〈당기〉" 등 꺾쇠 블록 제거 (위치 무관)
    s = re.sub(r"[<〈][^>〉]*[>〉]", "", s).strip()
    # 내부 공백 압축
    s = re.sub(r"\s+", "", s)
    return s if s else None


def _parse_data_by_year(data_list: list, yymm_list: list) -> Dict[str, Dict[str, float]]:
    """cF* JSON의 DATA 리스트를 {연도: {항목명: 값}} 형식으로 변환.

    DATA1~DATA5 = 최근 5년 연간
    DATA6 = 1년 컨센서스 예상 (있는 경우)

    YYMM 리스트의 형식 예: '2021/12<br />(IFRS연결)', '2026/12(E)<br />(IFRS연결)'
    """
    # 연도만 추출
    years = []
    for y in yymm_list:
        m = re.match(r"(\d{4})", str(y))
        years.append(m.group(1) if m else None)

    out: Dict[str, Dict[str, float]] = {}
    for item in data_list:
        name = _normalize_acc_nm(item.get("ACC_NM", ""))
        if name is None:
            continue
        # 같은 이름의 세부 항목이 여러 번 나오면 상위(LVL 낮음) 우선
        for i in range(1, 7):
            year = years[i - 1] if i - 1 < len(years) else None
            if not year:
                continue
            val = item.get(f"DATA{i}")
            if val is None:
                continue
            out.setdefault(year, {})
            # 이미 있으면 LVL이 낮은(상위) 항목 우선 → 덮어쓰지 않음
            if name not in out[year]:
                out[year][name] = float(val)
    return out


def get_balance_detail(code: str) -> Dict[str, Dict[str, float]]:
    """재무상태표 세부 (cF3002 rpt=1). 5년 + 2026E.

    Returns:
        {
            '2021': {'자산총계': 668500, '자본총계': 349125, '매출채권': 17877, ...},
            ...
            '2026': {...}  # 컨센서스
        }
    """
    encparam = _get_encparam("c1030001", code)
    if not encparam:
        return {}
    j = _fetch_cf_ajax("cF3002", code, rpt=1, encparam=encparam, referer_page="c1030001")
    if not j:
        return {}
    return _parse_data_by_year(j.get("DATA", []), j.get("YYMM", []))


def get_cashflow_detail(code: str) -> Dict[str, Dict[str, float]]:
    """현금흐름표 세부 (cF3002 rpt=2). 5년 + 2026E.

    Returns:
        {
            '2021': {'영업활동으로인한현금흐름': 73597, '유형자산의취득': 13195,
                     '유형자산감가상각비': 17004, '배당금(-)': -4009, ...},
            ...
        }
    """
    encparam = _get_encparam("c1030001", code)
    if not encparam:
        return {}
    j = _fetch_cf_ajax("cF3002", code, rpt=2, encparam=encparam, referer_page="c1030001")
    if not j:
        return {}
    return _parse_data_by_year(j.get("DATA", []), j.get("YYMM", []))


def get_financial_ratios(code: str) -> Dict[str, Dict[str, Dict[str, float]]]:
    """재무비율 5종 (cF4002 rpt=1~5). 5년 + 2026E.

    Returns:
        {
            'profitability': {'2021': {'ROE': 14.69, 'ROA': 7.48, ...}, ...},
            'growth':        {'2021': {'매출액증가율': 18.07, ...}, ...},
            'stability':     {'2021': {'부채비율': 91.48, '유동비율': 135.45, ...}, ...},
            'activity':      {'2021': {'재고자산회전율': ..., '매출채권회전율': ..., ...}, ...},
            'valuation':     {'2021': {'EPS': 11744, 'PER': ..., ...}, ...},
        }
    """
    encparam = _get_encparam("c1040001", code)
    if not encparam:
        return {}

    rpt_map = {
        1: "profitability",
        2: "growth",
        3: "stability",
        4: "activity",
        5: "valuation",
    }
    result = {}
    for rpt, key in rpt_map.items():
        j = _fetch_cf_ajax("cF4002", code, rpt=rpt, encparam=encparam, referer_page="c1040001")
        if not j:
            continue
        result[key] = _parse_data_by_year(j.get("DATA", []), j.get("YYMM", []))
    return result


def get_all_wisereport(code: str) -> Dict:
    """Wisereport 전체 데이터 (finsum_more + cF3002 + cF4002) 한 번에 수집."""
    return {
        "summary": get_all_naver_data(code),       # 컨센서스/Forward/주주/신용등급
        "balance": get_balance_detail(code),       # 재무상태표 5년 + 2026E
        "cashflow": get_cashflow_detail(code),     # 현금흐름표 5년 + 2026E
        "ratios": get_financial_ratios(code),      # 재무비율 5종 5년 + 2026E
    }


if __name__ == "__main__":
    import sys, json
    code = sys.argv[1] if len(sys.argv) > 1 else "000270"
    cmd = sys.argv[2] if len(sys.argv) > 2 else "all"

    if cmd == "summary":
        print(json.dumps(get_all_naver_data(code), ensure_ascii=False, indent=2))
    elif cmd == "balance":
        bs = get_balance_detail(code)
        for y in sorted(bs.keys()):
            print(f"\n=== {y} 재무상태표 (핵심) ===")
            fields = ["자산총계", "유동자산", "재고자산", "매출채권", "비유동자산",
                     "유형자산", "부채총계", "유동부채", "매입채무", "단기차입금",
                     "비유동부채", "장기차입금", "자본총계", "CAPEX", "순이자발생부채", "순부채"]
            for f in fields:
                if f in bs[y]:
                    print(f"  {f:20}: {bs[y][f]:>15,.0f}")
    elif cmd == "cashflow":
        cf = get_cashflow_detail(code)
        for y in sorted(cf.keys()):
            print(f"\n=== {y} 현금흐름표 (핵심) ===")
            fields = ["영업활동으로인한현금흐름", "투자활동으로인한현금흐름", "재무활동으로인한현금흐름",
                     "유형자산감가상각비", "무형자산상각비", "법인세", "유형자산의취득",
                     "무형자산의취득", "배당금(-)"]
            for f in fields:
                if f in cf[y]:
                    print(f"  {f:30}: {cf[y][f]:>15,.0f}")
    elif cmd == "ratios":
        rs = get_financial_ratios(code)
        for section, years in rs.items():
            print(f"\n=== {section} ===")
            for y in sorted(years.keys())[:3]:
                print(f"  {y}:")
                for k, v in list(years[y].items())[:8]:
                    print(f"    {k}: {v}")
    else:
        print(json.dumps(get_all_wisereport(code), ensure_ascii=False, indent=2, default=str))
