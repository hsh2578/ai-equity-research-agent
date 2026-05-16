"""
한국투자증권 OpenAPI 데이터 수집 스크립트 (모의투자용)
- 현재가 조회
- 투자자별 매매동향 (외국인/기관/개인)
- 재무비율 조회
- 기간별 시세 조회
"""

import json
import requests
import threading
import time
import sys
from datetime import datetime, timedelta

# ============================================
# API 설정 -- .env 자동 로드 (프로젝트 → 상위 → 상위상위 순으로 탐색)
# ============================================
import os
from pathlib import Path

def _load_env_auto():
    """프로젝트 .env → 상위 폴더 .env 순으로 우선 로드 (이미 설정된 환경변수는 유지)"""
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / '.env',                # 프로젝트 루트 (주식 ai 리서치 리포트 에이전트/.env)
        here.parent.parent / '.env',         # 상위 폴더 (vibecoding/.env)
        here.parent.parent.parent / '.env',  # 상위상위
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                # 이미 shell 에서 export 된 값이 있으면 덮어쓰지 않음 (shell 우선)
                if k and v and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            pass

_load_env_auto()

KIS_APP_KEY = os.environ.get("KIS_APP_KEY", "")
KIS_APP_SECRET = os.environ.get("KIS_APP_SECRET", "")
KIS_BASE_URL = os.environ.get("KIS_BASE_URL", "https://openapi.koreainvestment.com:9443")
if not (KIS_APP_KEY and KIS_APP_SECRET):
    print("[WARN] KIS_APP_KEY / KIS_APP_SECRET 환경변수가 설정되지 않았습니다. 한국투자증권 OpenAPI 발급 후 설정하세요.", file=sys.stderr)

session = requests.Session()


# ============================================
# Rate Limiter
# ============================================
class RateLimiter:
    def __init__(self, max_per_sec):
        self.min_interval = 1.0 / max_per_sec
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            gap = self.last + self.min_interval - now
            if gap > 0:
                time.sleep(gap)
            self.last = time.monotonic()


limiter = RateLimiter(18)

# ============================================
# 토큰 관리
# ============================================
_token = None
_token_expires_at = None
_token_lock = threading.Lock()


_TOKEN_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".kis_token.json")


def _load_token_cache():
    """파일에서 토큰 캐시 로드. 만료되지 않았으면 재사용."""
    global _token, _token_expires_at
    if not os.path.exists(_TOKEN_CACHE_PATH):
        return False
    try:
        with open(_TOKEN_CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        expires = datetime.fromisoformat(data["expires_at"])
        if datetime.now() < expires - timedelta(minutes=10):
            _token = data["token"]
            _token_expires_at = expires
            return True
    except Exception:
        pass
    return False


def _save_token_cache(token, expires_at):
    try:
        with open(_TOKEN_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"token": token, "expires_at": expires_at.isoformat()}, f)
    except Exception:
        pass


def get_access_token():
    global _token, _token_expires_at
    with _token_lock:
        now = datetime.now()
        if _token and _token_expires_at and now < _token_expires_at - timedelta(minutes=5):
            return _token
        # 파일 캐시 확인 (프로세스 재시작 시)
        if _load_token_cache() and _token:
            return _token

        resp = session.post(
            f"{KIS_BASE_URL}/oauth2/tokenP",
            headers={"Content-Type": "application/json"},
            json={
                "grant_type": "client_credentials",
                "appkey": KIS_APP_KEY,
                "appsecret": KIS_APP_SECRET,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        _token = data["access_token"]
        _token_expires_at = now + timedelta(hours=23)
        _save_token_cache(_token, _token_expires_at)
        print(f"[OK] 토큰 발급 완료")
        return _token


def _make_headers(tr_id):
    return {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {get_access_token()}",
        "appkey": KIS_APP_KEY,
        "appsecret": KIS_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }


def api_get(api_url, tr_id, params):
    limiter.wait()
    resp = session.get(api_url, headers=_make_headers(tr_id), params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ============================================
# 1. 현재가 조회
# ============================================
def _safe_int(v, default=0):
    try: return int(v)
    except (ValueError, TypeError): return default

def _safe_float(v, default=0.0):
    try: return float(v)
    except (ValueError, TypeError): return default

def get_current_price(code: str) -> dict:
    """종목 현재가 및 기본 시세 조회"""
    code6 = str(code).zfill(6)
    url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    tr_id = "FHKST01010100"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code6,
    }
    data = api_get(url, tr_id, params)
    if data.get("rt_cd") != "0":
        return {"error": data.get("msg1", "조회 실패")}

    output = data.get("output", {})
    return {
        "종목명": output.get("hts_kor_isnm", ""),
        "현재가": _safe_int(output.get("stck_prpr")),
        "전일대비": _safe_int(output.get("prdy_vrss")),
        "등락률": _safe_float(output.get("prdy_ctrt")),
        "거래량": _safe_int(output.get("acml_vol")),
        "거래대금": _safe_int(output.get("acml_tr_pbmn")),
        "시가": _safe_int(output.get("stck_oprc")),
        "고가": _safe_int(output.get("stck_hgpr")),
        "저가": _safe_int(output.get("stck_lwpr")),
        "52주최고": _safe_int(output.get("stck_dryy_hgpr")),
        "52주최저": _safe_int(output.get("stck_dryy_lwpr")),
        "시가총액": _safe_int(output.get("hts_avls")),
        "PER": _safe_float(output.get("per")),
        "PBR": _safe_float(output.get("pbr")),
        "EPS": _safe_float(output.get("eps")),
        "BPS": _safe_float(output.get("bps")),
    }


# ============================================
# 2. 투자자별 매매동향
# ============================================
def get_investor_trend(code: str, days: int = 10) -> dict:
    """외국인/기관/개인 순매수 동향"""
    code6 = str(code).zfill(6)
    url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"
    tr_id = "FHKST01010900"
    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code6,
    }
    data = api_get(url, tr_id, params)
    if data.get("rt_cd") != "0":
        return {"error": data.get("msg1", "조회 실패")}

    items = data.get("output", [])
    if not items:
        return {"error": "데이터 없음"}

    recent = items[:days]
    foreign_net = 0
    institution_net = 0
    individual_net = 0
    detail = []

    for item in recent:
        f_buy = int(item.get("frgn_ntby_qty", 0) or 0)
        i_buy = int(item.get("orgn_ntby_qty", 0) or 0)
        p_buy = int(item.get("prsn_ntby_qty", 0) or 0)

        foreign_net += f_buy
        institution_net += i_buy
        individual_net += p_buy

        detail.append({
            "date": item.get("stck_bsop_date", ""),
            "외국인": f_buy,
            "기관": i_buy,
            "개인": p_buy,
        })

    return {
        "외국인_순매수": foreign_net,
        "기관_순매수": institution_net,
        "개인_순매수": individual_net,
        "detail": detail,
    }


# ============================================
# 3. 기간별 시세 (일봉)
# ============================================
def get_daily_price(code: str, days: int = 60) -> list:
    """최근 N일간 일봉 데이터"""
    code6 = str(code).zfill(6)
    url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
    tr_id = "FHKST03010100"

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    params = {
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code6,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": "D",
        "FID_ORG_ADJ_PRC": "1",
    }
    data = api_get(url, tr_id, params)
    if data.get("rt_cd") != "0":
        return []

    items = data.get("output2", [])
    result = []
    for item in items[:days]:
        result.append({
            "날짜": item.get("stck_bsop_date", ""),
            "시가": int(item.get("stck_oprc", 0)),
            "고가": int(item.get("stck_hgpr", 0)),
            "저가": int(item.get("stck_lwpr", 0)),
            "종가": int(item.get("stck_clpr", 0)),
            "거래량": int(item.get("acml_vol", 0)),
        })

    return result


# ============================================
# 4. 해외주식 현재가 조회
# ============================================
def get_us_current_price(ticker: str, excd: str = "NAS") -> dict:
    """미국 주식 현재가 조회
    excd: NAS=나스닥, NYS=뉴욕, AMS=아멕스
    """
    url = f"{KIS_BASE_URL}/uapi/overseas-price/v1/quotations/price"
    tr_id = "HHDFS00000300"
    params = {
        "AUTH": "",
        "EXCD": excd,
        "SYMB": ticker.upper(),
    }
    data = api_get(url, tr_id, params)
    if data.get("rt_cd") != "0":
        return {"error": data.get("msg1", "조회 실패")}

    output = data.get("output", {})
    return {
        "종목명": output.get("rsym", ""),
        "현재가": _safe_float(output.get("last")),
        "전일대비": _safe_float(output.get("diff")),
        "등락률": _safe_float(output.get("rate")),
        "거래량": _safe_int(output.get("tvol")),
        "시가": _safe_float(output.get("open")),
        "고가": _safe_float(output.get("high")),
        "저가": _safe_float(output.get("low")),
        "52주최고": _safe_float(output.get("h52p")),
        "52주최저": _safe_float(output.get("l52p")),
        "PER": _safe_float(output.get("perx")),
        "PBR": _safe_float(output.get("pbrx")),
        "EPS": _safe_float(output.get("epsx")),
        "BPS": _safe_float(output.get("bpsx")),
        "시가총액": output.get("tomv", ""),
    }


# ============================================
# 5. 해외주식 일봉 조회
# ============================================
def get_us_daily_price(ticker: str, excd: str = "NAS", days: int = 100) -> list:
    """미국 주식 기간별 일봉 데이터"""
    from datetime import datetime, timedelta
    url = f"{KIS_BASE_URL}/uapi/overseas-price/v1/quotations/dailyprice"
    tr_id = "HHDFS76240000"

    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")

    params = {
        "AUTH": "",
        "EXCD": excd,
        "SYMB": ticker.upper(),
        "GUBN": "0",  # 0:일, 1:주, 2:월
        "BYMD": end_date,
        "MODP": "1",  # 수정주가
    }
    data = api_get(url, tr_id, params)
    if data.get("rt_cd") != "0":
        return []

    items = data.get("output2", [])
    result = []
    for item in items[:days]:
        if item.get("xymd"):
            result.append({
                "날짜": item.get("xymd", ""),
                "시가": float(item.get("open", 0)),
                "고가": float(item.get("high", 0)),
                "저가": float(item.get("low", 0)),
                "종가": float(item.get("clos", 0)),
                "거래량": int(item.get("tvol", 0)),
            })
    return result


# ============================================
# 재무 엔드포인트 (국내주식 종목정보)
# ============================================
#
# 공식 KIS Open API 재무 엔드포인트 7개.
# DART 파싱 지옥을 대체하는 핵심 함수들.
# 모두 6년+ 연간 데이터를 단일 요청으로 반환한다.
#
# fid_div_cls_code: '0' = 연간, '1' = 분기
# fid_cond_mrkt_div_code: 'J' = 주식(KOSPI/KOSDAQ)
# ============================================

def _fetch_finance(path: str, tr_id: str, code: str, period: str = "0") -> list:
    """KIS 재무 API 공통 호출. 실패 시 [] 반환."""
    url = f"{KIS_BASE_URL}/uapi/domestic-stock/v1/finance/{path}"
    headers = _make_headers(tr_id)
    params = {
        "FID_DIV_CLS_CODE": period,
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": code,
    }
    limiter.wait()
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("rt_cd") != "0":
            return []
        out = data.get("output", [])
        if isinstance(out, dict):
            out = [out]
        return out
    except Exception:
        return []


def get_income_statement(code: str, period: str = "0") -> list:
    """손익계산서. 연간 6년 / 분기 N분기.
    필드: stac_yymm, sale_account(매출), sale_cost(매출원가),
         sale_totl_prfi(매출총이익), bsop_prti(영업이익),
         op_prfi(경상이익), thtr_ntin(당기순이익)
    """
    return _fetch_finance("income-statement", "FHKST66430200", code, period)


def get_balance_sheet(code: str, period: str = "0") -> list:
    """대차대조표.
    필드: cras(유동자산), fxas(비유동자산), total_aset(총자산),
         flow_lblt(유동부채), fix_lblt(비유동부채), total_lblt(총부채),
         cpfn(자본금), cfp_surp(자본잉여금), prfi_surp(이익잉여금),
         total_cptl(자본총계)
    """
    return _fetch_finance("balance-sheet", "FHKST66430100", code, period)


def get_financial_ratio(code: str, period: str = "0") -> list:
    """재무비율 (통합).
    필드: grs(매출성장률), bsop_prfi_inrt(영업이익증가율),
         ntin_inrt(순이익증가율), roe_val(ROE), eps, sps(주당매출액),
         bps, rsrv_rate(유보율), lblt_rate(부채비율)
    """
    return _fetch_finance("financial-ratio", "FHKST66430300", code, period)


def get_profit_ratio(code: str, period: str = "0") -> list:
    """수익성비율.
    필드: cptl_ntin_rate(총자산순이익률/ROA),
         self_cptl_ntin_inrt(자기자본순이익률/ROE),
         sale_ntin_rate(매출액순이익률/NPM),
         sale_totl_rate(매출총이익률)
    """
    return _fetch_finance("profit-ratio", "FHKST66430400", code, period)


def get_stability_ratio(code: str, period: str = "0") -> list:
    """안정성비율.
    필드: lblt_rate(부채비율), bram_depn(차입금의존도),
         crnt_rate(유동비율), quck_rate(당좌비율)
    """
    return _fetch_finance("stability-ratio", "FHKST66430600", code, period)


def get_growth_ratio(code: str, period: str = "0") -> list:
    """성장성비율.
    필드: grs(매출성장률), bsop_prfi_inrt(영업이익증가율),
         equt_inrt(자기자본증가율), totl_aset_inrt(총자산증가율)
    """
    return _fetch_finance("growth-ratio", "FHKST66430800", code, period)


def get_other_major_ratios(code: str, period: str = "0") -> list:
    """기타주요비율. 밸류에이션 핵심 지표 포함.
    필드: payout_rate(배당성향), eva(경제적부가가치),
         ebitda, ev_ebitda
    """
    return _fetch_finance("other-major-ratios", "FHKST66430500", code, period)


def get_all_financials(code: str, period: str = "0") -> dict:
    """재무 7개 엔드포인트를 한 번에 호출하여 통합 반환.

    Returns:
        {
            "income": [...],       # 손익계산서
            "balance": [...],      # 대차대조표
            "ratio": [...],        # 재무비율
            "profit": [...],       # 수익성
            "stability": [...],    # 안정성
            "growth": [...],       # 성장성
            "other": [...],        # 기타 (EBITDA 등)
        }
    """
    return {
        "income": get_income_statement(code, period),
        "balance": get_balance_sheet(code, period),
        "ratio": get_financial_ratio(code, period),
        "profit": get_profit_ratio(code, period),
        "stability": get_stability_ratio(code, period),
        "growth": get_growth_ratio(code, period),
        "other": get_other_major_ratios(code, period),
    }


# ============================================
# 테스트
# ============================================
def test_kis(code: str):
    print(f"\n{'='*60}")
    print(f"  한국투자증권 API 테스트: {code}")
    print(f"{'='*60}\n")

    # 1. 현재가
    print("[1] 현재가 조회...")
    price = get_current_price(code)
    if "error" not in price:
        print(f"    종목명: {price['종목명']}")
        print(f"    현재가: {price['현재가']:,}원 ({price['등락률']:+.2f}%)")
        print(f"    거래량: {price['거래량']:,}")
        print(f"    시가총액: {price['시가총액']:,}억원")
        print(f"    PER: {price['PER']:.1f}  PBR: {price['PBR']:.2f}")
        print(f"    EPS: {price['EPS']:,.0f}  BPS: {price['BPS']:,.0f}")
        print(f"    52주 최고/최저: {price['52주최고']:,} / {price['52주최저']:,}")
    else:
        print(f"    에러: {price['error']}")

    # 2. 투자자별 매매동향
    print("\n[2] 투자자별 매매동향 (최근 10일)...")
    trend = get_investor_trend(code, 10)
    if "error" not in trend:
        print(f"    외국인 순매수: {trend['외국인_순매수']:,}주")
        print(f"    기관 순매수:   {trend['기관_순매수']:,}주")
        print(f"    개인 순매수:   {trend['개인_순매수']:,}주")
        print(f"    {'─'*40}")
        print(f"    {'날짜':<12} {'외국인':>10} {'기관':>10} {'개인':>10}")
        for d in trend['detail'][:5]:
            print(f"    {d['date']:<12} {d['외국인']:>10,} {d['기관']:>10,} {d['개인']:>10,}")
    else:
        print(f"    에러: {trend['error']}")

    # 3. 기간별 시세
    print("\n[3] 최근 일봉 (5일)...")
    daily = get_daily_price(code, 10)
    if daily:
        print(f"    {'날짜':<12} {'종가':>10} {'거래량':>12}")
        for d in daily[:5]:
            print(f"    {d['날짜']:<12} {d['종가']:>10,} {d['거래량']:>12,}")
    else:
        print("    데이터 없음")

    print(f"\n{'='*60}")
    print("  한국투자증권 API 테스트 완료!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "005930"  # 삼성전자
    test_kis(code)
