"""ta_common.py -- /research-ta 공용 헬퍼 (Task 1).

10개 ta_*.py 수집/검사 스크립트가 전부 이 모듈을 import 한다. 작고 안정적으로
유지한다 -- 여기서 나는 버그는 모든 스크립트에 번진다.

제공하는 것:
  - 경로: PROJECT_ROOT, ta_dir(), data_dir()
  - JSON: write_json()(원자적) / read_json()
  - 종목 식별: resolve_stock() (code 인자 -> analysis.json -> financial_summary.json
    -> FinanceDataReader 상장목록 -> KRX Open API 순으로 찾는다), name_variants()
  - KRX Open API 폴백: krx_http_call() / krx_call_with_fallback() (일별매매 교차검증 등
    다른 ta_*.py 에서도 재사용)
  - 반응 기사 필터: REACTION_PATTERNS / is_reaction_title()
  - 진행 기록: manifest_update() (ta/manifest.json)
  - 시각: KST / now_kst()
"""
import io
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

KST = timezone(timedelta(hours=9))


def now_kst():
    return datetime.now(KST)


# ==================== 경로 ====================

def _validate_name(stock_name):
    s = stock_name or ''
    if not s or '/' in s or '\\' in s or '..' in s:
        raise ValueError(f"stock_name 에 경로 구분자를 쓸 수 없음: {stock_name!r}")
    return s


def data_dir(stock_name):
    """data/{stock_name} 절대경로. 만들지 않는다."""
    _validate_name(stock_name)
    return os.path.join(PROJECT_ROOT, 'data', stock_name)


def ta_dir(stock_name):
    """data/{stock_name}/ta 절대경로. 없으면 만든다."""
    d = os.path.join(data_dir(stock_name), 'ta')
    os.makedirs(d, exist_ok=True)
    return d


# ==================== JSON ====================

def write_json(path, obj):
    """원자적 쓰기: 같은 폴더 임시파일 -> os.replace."""
    folder = os.path.dirname(path) or '.'
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.tmp_', suffix='.json')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def read_json(path, default=None):
    """파일 없으면 default. JSON 이 깨졌으면 예외를 그대로 올린다(삼키지 않는다)."""
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


# ==================== 종목 식별 ====================

# fdr.StockListing('KRX') 는 프로덕션에서 JSONDecodeError 로 죽어 있다(2026-09 확인).
# 'KRX-DESC' 가 살아있는 대안이고 Market/SettleMonth 컬럼을 함께 준다.
# volatility_beta.py 가 이미 code->market 조회를 7일 디스크 캐시로 구현해 뒀으므로
# (KRX-DESC 조회 + pykrx 폴백), 코드가 이미 있는 경우의 시장 판정은 그걸 재사용하고
# 여기서 새 fetch/cache 계층을 만들지 않는다. 이름->코드 매칭과 settle_month 는
# 그 캐시가 안 주는 정보라 listing(주입 또는 KRX-DESC 직접 조회)이 그대로 필요하다.

def _fetch_listing_df(attempts):
    """FinanceDataReader.StockListing('KRX-DESC') 시도. 실패하면 None + attempts 기록."""
    try:
        import FinanceDataReader as fdr
        return fdr.StockListing('KRX-DESC')
    except Exception as e:
        attempts.append(f'FDR KRX-DESC 조회 실패: {type(e).__name__}: {e}')
        return None


def _detect_market_cached(stock_code, attempts):
    """volatility_beta.detect_market() 재사용 (7일 캐시 + pykrx 폴백). 새 fetch 안 만든다."""
    try:
        import volatility_beta as _vb
    except ImportError as e:
        attempts.append(f'volatility_beta import 실패: {type(e).__name__}: {e}')
        return None
    try:
        return _vb.detect_market(stock_code)
    except Exception as e:
        attempts.append(f'volatility_beta.detect_market 실패: {type(e).__name__}: {e}')
        return None


def _settle_month(row):
    v = row.get('SettleMonth') if hasattr(row, 'get') else None
    if v is None or v != v:   # v != v 는 NaN (pandas 미import)
        return None
    v = str(v).strip()
    return v or None


# market 문자열 -> (benchmark_code, benchmark_name, yahoo_suffix 또는 None, note 또는 None).
# 모르는 값이면 None -- 잘못된 벤치마크로 조용히 넘어가면 이후 모든 초과수익률이 오염된다.
def _market_bucket(market):
    m = (market or '').upper()
    if m.startswith('KOSDAQ'):          # 'KOSDAQ', 'KOSDAQ GLOBAL' 전부 포함
        return '229200', 'KODEX 코스닥150', 'KQ', None
    if m == 'KOSPI':
        return '069500', 'KODEX 200', 'KS', None
    if m == 'KONEX':
        return ('069500', 'KODEX 200', None,
                'KONEX 상장종목: 야후 티커 매핑 없음, 벤치마크는 KOSPI ETF(069500) 잠정 적용')
    return None


# ==================== KRX Open API 폴백 (Task 14) ====================
# resolve_stock 이 기존 경로(analysis/financial_summary/KRX-DESC/detect_market)로
# 시장을 못 정했을 때만 쓰는 마지막 수단. 승인된 6개 엔드포인트 중 종목기본정보
# 2개(sto/stk_isu_base_info=KOSPI, sto/ksq_isu_base_info=KOSDAQ)만 쓴다.
# 참고(읽기 전용, import 안 함): 알고픽/src/algopick/data/krx_open.py 의
# _call_with_fallback 규칙(17시 이전=전 거래일, 평일만, 최대 5회 폴백)을 그대로 옮긴다.

KRX_BASE = 'https://data-dbg.krx.co.kr/svc/apis/'


def _krx_api_key():
    """KRX_API_KEY 환경변수. 없으면 마스터 .env 를 한 번 로드해 재시도. 값은 절대 출력하지 않는다."""
    key = os.environ.get('KRX_API_KEY')
    if key:
        return key
    sys.path.insert(0, 'C:/Users/hsh/Desktop')
    from env_loader import load_env
    load_env()
    return os.environ.get('KRX_API_KEY') or ''


def krx_http_call(path, basDd, timeout=15):
    """KRX Open API 단일 호출(기본 구현, krx_call 이 주입되지 않았을 때 쓰인다).
    키 없음/HTTP 오류는 예외로 올린다 -- 호출자(krx_call_with_fallback)가 사유를
    attempts 에 구조화해 남긴다(여기서 삼키지 않는다)."""
    import ssl
    import urllib.request

    key = _krx_api_key()
    if not key:
        raise RuntimeError('KRX_API_KEY 없음')
    url = f'{KRX_BASE}{path}?basDd={basDd}'
    req = urllib.request.Request(url, headers={'AUTH_KEY': key, 'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as r:
        body = json.loads(r.read().decode('utf-8', 'replace'))
    return body.get('OutBlock_1') or []


def krx_call_with_fallback(path, krx_call=None, max_lookback=5, now=None):
    """basDd 를 오늘(평일 17시 이전이면 전 거래일)부터 평일만 골라 최대 max_lookback 회
    조회하고, 빈 응답이면 하루씩 더 거슬러 올라간다(주말/공휴일 대응, 알고픽
    krx_open._call_with_fallback 과 동일 규칙). krx_call(path, basDd) 주입 가능
    (테스트용 -- 기본은 krx_http_call, 네트워크 호출). 반환: (rows, 마지막으로 시도한
    basDd, 실패사유 리스트) -- rows 는 전부 실패/빈 응답이면 []."""
    call = krx_call or krx_http_call
    n = now or now_kst()
    d = n.date()
    if d.weekday() < 5 and n.hour < 17:
        d -= timedelta(days=1)
    reasons = []
    last_basdd = None
    for _ in range(max_lookback):
        while d.weekday() >= 5:
            d -= timedelta(days=1)
        basDd = d.strftime('%Y%m%d')
        last_basdd = basDd
        try:
            rows = call(path, basDd)
        except Exception as e:
            reasons.append(f'KRX {path} {basDd}: {type(e).__name__}: {e}')
            rows = []
        if rows:
            return rows, basDd, reasons
        d -= timedelta(days=1)
    reasons.append(f'KRX {path}: {max_lookback}회 조회 모두 빈 응답')
    return [], last_basdd, reasons


def _krx_open_market_lookup(stock_name, found_code, krx_call=None):
    """KRX 기본정보 2개 엔드포인트로 code/market 판별. found_code 가 있으면 그 코드가
    있는 시장만 찾고, 없으면 이름(정식명 ISU_NM 또는 약칭 ISU_ABBRV 일치)으로 code 까지
    찾는다. 반환: (code 또는 None, market 또는 None, 실패사유 리스트)."""
    reasons = []
    for path, market in (('sto/stk_isu_base_info', 'KOSPI'), ('sto/ksq_isu_base_info', 'KOSDAQ')):
        rows, _basDd, why = krx_call_with_fallback(path, krx_call=krx_call)
        reasons.extend(why)
        for row in rows:
            code = str(row.get('ISU_SRT_CD') or '').strip().zfill(6)
            if not code or len(code) != 6 or not code.isdigit():
                continue
            if found_code:
                if code == found_code:
                    return found_code, market, reasons
            else:
                name = str(row.get('ISU_NM') or '').strip()
                abbr = str(row.get('ISU_ABBRV') or '').strip()
                if stock_name in (name, abbr):
                    return code, market, reasons
    return None, None, reasons


def resolve_stock(stock_name, code=None, listing=None, krx_call=None):
    """종목명 -> 코드/시장/벤치마크/야후티커/결산월. 코드 탐색 순서: code 인자 ->
    analysis.json -> financial_summary.json -> KRX-DESC 상장목록(listing 주입 가능,
    테스트용) -> **KRX Open API**(시장을 끝내 못 정했을 때만, krx_call 주입 가능).
    market 은 위 소스 -> volatility_beta.detect_market() -> KRX Open API 순으로 채운다.
    코드를 못 찾거나 market 을 확정할 수 없으면(빈 문자열로 조용히 넘어가지 않는다)
    LookupError. KRX Open API 로 채웠으면 source 는 'krx_open'.
    """
    attempts = []
    found_code = None
    found_market = ''
    settle_month = None
    source = ''

    if code:
        found_code = str(code).zfill(6)
        source = 'code_arg'
    else:
        attempts.append('code 인자 없음')

    if not found_code:
        p = os.path.join(PROJECT_ROOT, 'scripts', f'analysis_{stock_name}.json')
        meta = {}
        if os.path.exists(p):
            try:
                meta = (read_json(p, {}) or {}).get('meta', {}) or {}
            except Exception as e:
                attempts.append(f'analysis.json 파싱 실패: {type(e).__name__}: {e}')
                meta = {}
        else:
            attempts.append(f'{p} 없음')
        sc = meta.get('stock_code')
        if sc:
            found_code = str(sc).zfill(6)
            found_market = str(meta.get('market') or '')
            source = 'analysis_json'
        elif meta:
            attempts.append('analysis.json meta.stock_code 없음')

    if not found_code:
        fp = os.path.join(data_dir(stock_name), 'financial_summary.json')
        if os.path.exists(fp):
            try:
                d = read_json(fp, {}) or {}
            except Exception as e:
                attempts.append(f'financial_summary.json 파싱 실패: {type(e).__name__}: {e}')
                d = {}
            sc2 = (d.get('meta', {}) or {}).get('stock_code')
            if sc2:
                found_code = str(sc2).zfill(6)
                source = 'financial_summary'
            else:
                attempts.append('financial_summary.json meta.stock_code 없음')
        else:
            attempts.append(f'{fp} 없음')

    # 이름->코드 매칭이 필요할 때만 listing 을 쓴다(주입 우선, 없으면 KRX-DESC 직접 조회).
    # 코드가 이미 있는데 listing 을 호출자가 안 줬다면 여기서 새로 fetch 하지 않는다
    # (market 판정은 아래에서 detect_market 캐시를 쓰고, settle_month 는 best-effort 로 None).
    df = listing
    if df is None and not found_code:
        df = _fetch_listing_df(attempts)

    if df is not None:
        try:
            if not found_code:
                hit = df[df['Name'] == stock_name]
                if not hit.empty:
                    row = hit.iloc[0]
                    found_code = str(row['Code']).zfill(6)
                    if not found_market:
                        found_market = str(row.get('Market') or '')
                    settle_month = _settle_month(row)
                    source = source or 'fdr_listing'
                else:
                    attempts.append('KRX-DESC 상장목록에 이름 일치 없음')
            elif settle_month is None or not found_market:
                hit2 = df[df['Code'].astype(str).str.zfill(6) == found_code]
                if not hit2.empty:
                    row2 = hit2.iloc[0]
                    if not found_market:
                        found_market = str(row2.get('Market') or '')
                    if settle_month is None:
                        settle_month = _settle_month(row2)
        except Exception as e:
            attempts.append(f'상장목록 조회 중 오류: {type(e).__name__}: {e}')

    if not found_code:
        kcode, kmarket, kreasons = _krx_open_market_lookup(stock_name, None, krx_call=krx_call)
        attempts.extend(kreasons)
        if kcode:
            found_code = kcode
            if kmarket:
                found_market = kmarket
            source = 'krx_open'

    if not found_code:
        raise LookupError(f"{stock_name}: 종목코드를 찾을 수 없음 -- " + ' / '.join(attempts))

    if not found_market:
        dm = _detect_market_cached(found_code, attempts)
        if dm:
            found_market = dm

    if not found_market:
        kcode2, kmarket2, kreasons2 = _krx_open_market_lookup(stock_name, found_code, krx_call=krx_call)
        attempts.extend(kreasons2)
        if kmarket2:
            found_market = kmarket2
            source = 'krx_open'

    bucket = _market_bucket(found_market)
    if bucket is None:
        raise LookupError(
            f"{stock_name}({found_code}): market 을 확정할 수 없음(market={found_market!r}) -- "
            + ' / '.join(attempts))
    benchmark_code, benchmark_name, yahoo_suffix, note = bucket

    return {
        'name': stock_name,
        'code': found_code,
        'market': found_market,
        'benchmark_code': benchmark_code,
        'benchmark_name': benchmark_name,
        'yahoo': f'{found_code}.{yahoo_suffix}' if yahoo_suffix else None,
        'settle_month': settle_month,
        'source': source or 'unknown',
        'note': note,
    }


def name_variants(stock_name):
    """corp_name_resolver.variants() 를 그대로 돌려준다. import 실패 시 [stock_name]."""
    try:
        import corp_name_resolver as _cnr
    except ImportError:
        return [stock_name]
    return _cnr.variants(stock_name)


# ==================== 반응 기사 필터 ====================

REACTION_PATTERNS = (
    '특징주', '급등', '급락', '상한가', '하한가', '신고가', '신저가',
    '강세', '약세', '장중', '마감시황', '오전시황', '[시황]', '52주',
)

# 실측 누락(Task 14): "에프에스티 주가, 4월 30일 42,500원 1.62% 하락 마감" 이
# 위 substring 목록의 '주가 '(공백 포함) 를 못 잡아 news 로 잘못 분류됐다(제목이
# "주가,"). substring 대신 정규식으로 승격: 구두점이 붙은 "주가" / "N.N% 상승·하락·
# 급등·급락" / "상승·하락 마감" 을 잡는다.
_REACTION_REGEXES = tuple(re.compile(p) for p in (
    r'주가\s*[,.:]?',
    r'\d+(\.\d+)?%\s*(상승|하락|급등|급락)',
    r'(상승|하락)\s*마감',
    r'\d+(\.\d+)?%\s*[↑↓▲▼]',   # "에프에스티 10%↑ ..." -- 화살표 등락 표기 (컨트롤러 추가 실측)
    r'[↑↓▲▼]\s*\d+(\.\d+)?%',
))


def is_reaction_title(title):
    """주가 움직임의 '원인' 이 아니라 '결과' 를 다루는 기사 제목인가."""
    t = title or ''
    if any(p in t for p in REACTION_PATTERNS):
        return True
    return any(r.search(t) for r in _REACTION_REGEXES)


# ==================== 진행 기록 ====================

_MANIFEST_STATUSES = ('ok', 'failed', 'skipped')


def manifest_update(stock_name, step, status, **detail):
    """ta/manifest.json 의 steps[step] 갱신(원자적). 갱신된 전체 dict 반환."""
    if status not in _MANIFEST_STATUSES:
        raise ValueError(f"status 는 {_MANIFEST_STATUSES} 중 하나여야 함: {status!r}")
    path = os.path.join(ta_dir(stock_name), 'manifest.json')
    manifest = read_json(path, {}) or {}
    steps = manifest.setdefault('steps', {})
    entry = {'status': status, 'at': now_kst().isoformat()}
    entry.update(detail)
    steps[step] = entry
    write_json(path, manifest)
    return manifest
