"""
매크로(거시) 실측 시계열 수집 모듈 -- FRED(미 연준) + ECOS(한국은행)

## 왜 있나

리포트의 산업/거시 서술이 전부 WebSearch 요약이라 "언제 기준 숫자인지" 가 흔들렸다.
"미 10년물 4%대", "환율 1,300원대" 같은 서술은 출처도 시점도 없다.
이 모듈은 그것을 **날짜가 박힌 실측 시계열**로 대체한다.

## 쓰는 법

CLI:
    python scripts/macro_data.py US                      # 미국 매크로 스냅샷
    python scripts/macro_data.py KR                      # 한국 매크로 스냅샷
    python scripts/macro_data.py US --series DGS10,CPIAUCSL
    python scripts/macro_data.py KR --series base_rate,usdkrw
    python scripts/macro_data.py US --json                # 표 대신 JSON 을 stdout 으로

    출력 파일: data/_macro_US.json / data/_macro_KR.json

import:
    from macro_data import build_snapshot
    snap = build_snapshot('US')
    snap['series']['ust10y']['latest']       # 4.77
    snap['series']['ust10y']['latest_date']  # '2026-09-03'
    snap['series']['ust10y']['change_12m']   # 전년 대비 %p

## 조용한 실패 금지 (이 프로젝트 최우선 원칙)

FnGuide 가 URL 이전으로 죽었는데 `except Exception: return None` 이 삼켜서
몇 달간 아무도 몰랐다. 같은 사고를 막기 위해 이 모듈은:

  - 실패를 `MacroError(reason, message, **detail)` 로 구조화한다
    (reason: no_api_key / network / http_status / bad_json / bad_schema /
             api_error / no_data / wrong_series / unexpected)
  - **응답이 왔어도 관측치가 0개면 실패**로 처리한다
  - ECOS 는 인증 오류/데이터 없음에도 **HTTP 200** 을 주고 본문에 RESULT 블록만 넣는다.
    상태코드만 보면 성공으로 오인하므로 본문을 반드시 검사한다 (실측 확인, 2026-09)
  - 값이 상식 범위를 벗어나면(금리 음수/100 초과 등) `warnings` 에 남긴다
  - 시계열이 오래 멈춰 있으면(일별 10일+, 월별 100일+) 신선도 경고를 남긴다
    -- 소스가 조용히 죽은 것을 탐지하는 장치다
  - 실패한 지표는 결과에서 **사라지지 않고** `ok: False` + `error` 로 남는다
  - 결과 JSON 에는 항상 `_collected_at` 과 `warnings` 가 들어간다
  - 실패 진단은 모듈 전역 `LAST_ERRORS` 에 축적되고 stderr 로도 출력된다
  - `MACRO_STRICT=1` 환경변수를 주면 하나라도 실패 시 CLI 종료코드가 1 이 된다

## 데이터 출처

  - FRED (Federal Reserve Bank of St. Louis)  https://fred.stlouisfed.org
    api.stlouisfed.org/fred/series/observations  -- FRED_API_KEY 필요
  - ECOS (한국은행 경제통계시스템)  https://ecos.bok.or.kr
    ecos.bok.or.kr/api/StatisticSearch/...      -- BOK_ECOS_API_KEY 필요

ECOS 통계표/항목 코드는 2026-09 실호출로 확인한 값이다:
    722Y001 / 0101000   한국은행 기준금리          (월)
    731Y001 / 0000001   원/달러 매매기준율          (일)
    901Y009 / 0         소비자물가지수 총지수(2020=100) (월)
    817Y002 / 010200000 국고채 3년물               (일)
"""

import argparse
import calendar
import datetime as dt
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


# ============================================================================
# .env 자동 로드 (scripts/../.env -> 상위 -> 상위상위). kis_api.py 와 동일 규칙.
# 이미 셸에서 export 된 값이 있으면 그것을 우선한다.
# ============================================================================
def _load_env_auto() -> None:
    here = Path(__file__).resolve().parent
    candidates = [
        here.parent / '.env',
        here.parent.parent / '.env',
        here.parent.parent.parent / '.env',
    ]
    for env_path in candidates:
        if not env_path.exists():
            continue
        try:
            for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k.startswith('export '):
                    k = k[len('export '):].strip()
                if k and v and k not in os.environ:
                    os.environ[k] = v
        except OSError:
            pass


_load_env_auto()

FRED_URL = 'https://api.stlouisfed.org/fred/series/observations'
ECOS_URL = 'https://ecos.bok.or.kr/api/StatisticSearch'

# 신선도 기준 (이보다 오래 멈춰 있으면 소스가 죽었을 가능성)
STALE_DAYS = {'D': 10, 'M': 100}

# 3개월/12개월 변화를 내려면 최소 그만큼의 과거가 필요하다. 여유 있게 받는다.
DEFAULT_LOOKBACK_MONTHS = 26


# ============================================================================
# 실패 표현
# ============================================================================
class MacroError(Exception):
    """매크로 수집 실패. 왜 실패했는지를 구조화해 들고 다닌다."""

    def __init__(self, reason: str, message: str, **detail):
        self.reason = reason
        self.message = message
        self.detail = dict(detail)
        super().__init__(f'[{reason}] {message}')

    def as_dict(self) -> Dict[str, Any]:
        d = dict(self.detail)
        d['reason'] = self.reason
        d['message'] = self.message
        return d


LAST_ERRORS: List[Dict[str, Any]] = []


# ============================================================================
# 지표 카탈로그
#   change_mode: 'diff' = 절대 변화(%p, 금리/실업률)  /  'pct' = 상대 변화(%, 지수/가격)
#   sane       : (하한, 상한) -- 벗어나면 경고. 값을 버리지는 않는다.
#   yoy        : True 면 전년동기 대비 % 를 별도 필드로 낸다 (물가지수용)
# ============================================================================
US_SERIES: Dict[str, Dict[str, Any]] = {
    'policy_rate': {
        'source': 'FRED', 'series_id': 'FEDFUNDS', 'label': '미 연방기금금리(실효)',
        'unit': '%', 'freq': 'M', 'change_mode': 'diff', 'sane': (-1.0, 25.0)},
    'ust10y': {
        'source': 'FRED', 'series_id': 'DGS10', 'label': '미 국채 10년물',
        'unit': '%', 'freq': 'D', 'change_mode': 'diff', 'sane': (-1.0, 25.0)},
    'ust2y': {
        'source': 'FRED', 'series_id': 'DGS2', 'label': '미 국채 2년물',
        'unit': '%', 'freq': 'D', 'change_mode': 'diff', 'sane': (-1.0, 25.0)},
    'yield_spread': {
        'source': 'FRED', 'series_id': 'T10Y2Y', 'label': '장단기 스프레드(10Y-2Y)',
        'unit': '%p', 'freq': 'D', 'change_mode': 'diff', 'sane': (-10.0, 10.0)},
    'cpi': {
        'source': 'FRED', 'series_id': 'CPIAUCSL', 'label': '미 소비자물가지수(1982-84=100)',
        'unit': 'pt', 'freq': 'M', 'change_mode': 'pct', 'sane': (50.0, 2000.0), 'yoy': True},
    'unemployment': {
        'source': 'FRED', 'series_id': 'UNRATE', 'label': '미 실업률',
        'unit': '%', 'freq': 'M', 'change_mode': 'diff', 'sane': (0.0, 40.0)},
    'dollar_index': {
        'source': 'FRED', 'series_id': 'DTWEXBGS', 'label': '달러인덱스(광의, 2006=100)',
        'unit': 'pt', 'freq': 'D', 'change_mode': 'pct', 'sane': (30.0, 300.0),
        # DTWEXBGS 는 일별 시계열이지만 FRED 게시가 주 1회(금요일 기준)라
        # 일별 10일 기준을 그대로 쓰면 매주 거짓 경고가 난다 (2026-09 실측)
        'stale_days': 21},
    'wti': {
        'source': 'FRED', 'series_id': 'DCOILWTICO', 'label': 'WTI 유가',
        'unit': '달러/배럴', 'freq': 'D', 'change_mode': 'pct', 'sane': (0.0, 500.0)},
    'vix': {
        'source': 'FRED', 'series_id': 'VIXCLS', 'label': 'VIX 변동성지수',
        'unit': 'pt', 'freq': 'D', 'change_mode': 'pct', 'sane': (0.0, 200.0)},
}

KR_SERIES: Dict[str, Dict[str, Any]] = {
    'base_rate': {
        'source': 'ECOS', 'stat_code': '722Y001', 'item_code': '0101000', 'cycle': 'M',
        'label': '한국은행 기준금리', 'unit': '%', 'freq': 'M',
        'change_mode': 'diff', 'sane': (-1.0, 25.0)},
    'usdkrw': {
        'source': 'ECOS', 'stat_code': '731Y001', 'item_code': '0000001', 'cycle': 'D',
        'label': '원/달러 환율(매매기준율)', 'unit': '원', 'freq': 'D',
        'change_mode': 'pct', 'sane': (500.0, 3000.0)},
    'cpi': {
        'source': 'ECOS', 'stat_code': '901Y009', 'item_code': '0', 'cycle': 'M',
        'label': '한국 소비자물가지수(2020=100)', 'unit': 'pt', 'freq': 'M',
        'change_mode': 'pct', 'sane': (50.0, 500.0), 'yoy': True},
    'ktb3y': {
        'source': 'ECOS', 'stat_code': '817Y002', 'item_code': '010200000', 'cycle': 'D',
        'label': '국고채 3년물', 'unit': '%', 'freq': 'D',
        'change_mode': 'diff', 'sane': (-1.0, 25.0)},
}

CATALOG = {'US': US_SERIES, 'KR': KR_SERIES}


# ============================================================================
# 날짜 헬퍼
# ============================================================================
def _to_date(s: str) -> dt.date:
    return dt.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))


def shift_months(date_str: str, months: int) -> str:
    """'2026-09-03' 에서 months 만큼 이동. 말일은 해당 월의 마지막 날로 보정."""
    d = _to_date(date_str)
    total = (d.year * 12 + (d.month - 1)) + months
    y, m = divmod(total, 12)
    m += 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return f'{y:04d}-{m:02d}-{day:02d}'


def normalize_ecos_time(t: str) -> str:
    """ECOS TIME 을 ISO 날짜로. 20260907 / 202608 / 2026Q3 / 2026 을 받는다."""
    t = str(t).strip()
    if len(t) == 8 and t.isdigit():
        return f'{t[0:4]}-{t[4:6]}-{t[6:8]}'
    if len(t) == 6 and t.isdigit():
        return f'{t[0:4]}-{t[4:6]}-01'
    if len(t) == 6 and t[4].upper() == 'Q':
        month = (int(t[5]) - 1) * 3 + 1
        return f'{t[0:4]}-{month:02d}-01'
    if len(t) == 4 and t.isdigit():
        return f'{t}-01-01'
    if len(t) == 5 and t[4].isdigit() and not t.isdigit():  # 반기 등 예외 표기
        return f'{t[0:4]}-01-01'
    raise MacroError('bad_schema', f'해석할 수 없는 ECOS TIME 형식: {t!r}', time=t)


def value_asof(obs: Sequence[Tuple[str, float]], target: str
               ) -> Optional[Tuple[str, float]]:
    """target 날짜 **이하** 중 가장 최근 관측치. 주말/휴일 공백을 자동으로 메운다.

    시계열 시작 이전을 물으면 None (0 이나 첫값으로 위조하지 않는다).
    """
    found = None
    for date, val in obs:
        if date <= target:
            found = (date, val)
        else:
            break
    return found


# ============================================================================
# 파서 -- 응답이 왔어도 관측치가 0개면 실패다
# ============================================================================
def parse_fred_observations(payload: Any) -> List[Tuple[str, float]]:
    """FRED /series/observations 응답 -> [(YYYY-MM-DD, float), ...] 오름차순."""
    if not isinstance(payload, dict):
        raise MacroError('bad_schema',
                         f'FRED 응답이 dict 가 아님 ({type(payload).__name__})',
                         head=str(payload)[:200])
    if payload.get('error_message') or payload.get('error_code'):
        raise MacroError('api_error', str(payload.get('error_message', 'FRED API 오류')),
                         code=payload.get('error_code'))
    raw = payload.get('observations')
    if not isinstance(raw, list):
        raise MacroError('bad_schema', "FRED 응답에 'observations' 배열이 없음",
                         keys=sorted(payload.keys())[:10])

    out: List[Tuple[str, float]] = []
    skipped = 0
    for o in raw:
        v = (o or {}).get('value')
        d = (o or {}).get('date')
        if v in (None, '', '.') or not d:   # '.' = 휴일/결측 (FRED 규약)
            skipped += 1
            continue
        try:
            out.append((str(d), float(v)))
        except (TypeError, ValueError):
            skipped += 1
    if not out:
        raise MacroError('no_data',
                         f'FRED 관측치 0개 (응답 {len(raw)}행, 결측 {skipped}행) '
                         '-- 응답은 왔지만 쓸 값이 없다',
                         rows=len(raw), skipped=skipped)
    out.sort()
    return out


def parse_ecos_rows(payload: Any, stat_code: Optional[str] = None
                    ) -> List[Tuple[str, float]]:
    """ECOS StatisticSearch 응답 -> [(YYYY-MM-DD, float), ...] 오름차순.

    ECOS 는 인증 실패/데이터 없음에도 HTTP 200 을 주고 본문에 RESULT 블록만 넣는다.
    상태코드만 믿으면 조용히 성공으로 오인하므로 여기서 반드시 걸러낸다.
    """
    if not isinstance(payload, dict):
        raise MacroError('bad_schema',
                         f'ECOS 응답이 dict 가 아님 ({type(payload).__name__})',
                         head=str(payload)[:200])
    if 'RESULT' in payload:
        res = payload.get('RESULT') or {}
        raise MacroError('api_error',
                         f"ECOS 오류 응답 (HTTP 200 이지만 RESULT 블록): "
                         f"{res.get('MESSAGE', '')}".strip(),
                         code=res.get('CODE'))
    node = payload.get('StatisticSearch')
    if not isinstance(node, dict):
        raise MacroError('bad_schema', "ECOS 응답에 'StatisticSearch' 노드가 없음",
                         keys=sorted(payload.keys())[:10])
    rows = node.get('row')
    if not isinstance(rows, list) or not rows:
        raise MacroError('no_data',
                         f"ECOS 관측치 0개 (list_total_count="
                         f"{node.get('list_total_count')}) -- 응답은 왔지만 행이 없다",
                         total=node.get('list_total_count'))

    if stat_code:
        got = {str(r.get('STAT_CODE')) for r in rows if r.get('STAT_CODE')}
        if got and stat_code not in got:
            raise MacroError('wrong_series',
                             f'요청 통계표 {stat_code} 인데 응답은 {sorted(got)}',
                             requested=stat_code, returned=sorted(got))

    out: List[Tuple[str, float]] = []
    skipped = 0
    for r in rows:
        v = (r or {}).get('DATA_VALUE')
        t = (r or {}).get('TIME')
        if v in (None, '', '-') or not t:
            skipped += 1
            continue
        try:
            out.append((normalize_ecos_time(t), float(v)))
        except (TypeError, ValueError):
            skipped += 1
    if not out:
        raise MacroError('no_data',
                         f'ECOS 유효 관측치 0개 (응답 {len(rows)}행 전부 결측)',
                         rows=len(rows), skipped=skipped)
    out.sort()
    return out


# ============================================================================
# 파생지표
# ============================================================================
def derive_metrics(obs: Sequence[Tuple[str, float]], spec: Dict[str, Any],
                   asof: Optional[str] = None) -> Dict[str, Any]:
    """최신값 + 3개월/12개월 전 대비 변화. 데이터가 없으면 None (0 으로 위조 금지)."""
    if not obs:
        raise MacroError('no_data', '파생지표 계산 대상 시계열이 비어 있음', rows=0)

    asof = asof or dt.date.today().isoformat()
    latest_date, latest = obs[-1]
    mode = spec.get('change_mode', 'pct')

    def _change(past: Optional[float]) -> Optional[float]:
        if past is None:
            return None
        if mode == 'diff':
            return round(latest - past, 4)
        if past == 0:
            return None
        return round((latest / past - 1) * 100, 4)

    m: Dict[str, Any] = {
        'latest': latest,
        'latest_date': latest_date,
        'obs_count': len(obs),
        'first_date': obs[0][0],
        'change_unit': ('%p' if spec.get('unit') == '%' else spec.get('unit', ''))
                       if mode == 'diff' else '%',
    }

    for months, tag in ((-3, '3m'), (-12, '12m')):
        target = shift_months(latest_date, months)
        hit = value_asof(obs, target)
        # 시계열이 target 보다 늦게 시작하면 hit is None -> 그대로 None 을 남긴다
        m[f'date_{tag}_ago'] = hit[0] if hit else None
        m[f'value_{tag}_ago'] = hit[1] if hit else None
        m[f'change_{tag}'] = _change(hit[1] if hit else None)

    if spec.get('yoy'):
        past = m['value_12m_ago']
        m['yoy'] = (round((latest / past - 1) * 100, 4)
                    if past not in (None, 0) else None)
        m['yoy_unit'] = '%'

    m['asof'] = asof
    return m


def sanity_warnings(alias: str, metrics: Dict[str, Any], spec: Dict[str, Any],
                    asof: Optional[str] = None) -> List[str]:
    """상식 범위 이탈 + 신선도 점검. 값을 버리지 않고 경고만 남긴다."""
    out: List[str] = []
    lo, hi = spec.get('sane', (float('-inf'), float('inf')))
    v = metrics.get('latest')
    if v is None:
        out.append('최신값이 없음')
        return out
    if not (lo <= v <= hi):
        out.append(f'값 {v} 이(가) 상식 범위 [{lo}, {hi}] 를 벗어남 '
                   f'- 지표 정의/단위 변경 의심')

    ld = metrics.get('latest_date')
    asof = asof or dt.date.today().isoformat()
    if ld:
        try:
            age = (_to_date(asof) - _to_date(ld)).days
        except (ValueError, IndexError):
            age = None
        if age is not None:
            limit = spec.get('stale_days') or STALE_DAYS.get(spec.get('freq', 'D'), 10)
            if age > limit:
                out.append(f'최신 관측이 {ld} 로 {age}일 지연 '
                           f'({spec.get("freq")} 시계열 기준 {limit}일 초과) '
                           '- 소스가 멈췄을 가능성')
    return out


# ============================================================================
# 네트워크 fetch
# ============================================================================
def _session():
    if requests is None:
        raise MacroError('network', 'requests 미설치 (pip install requests)')
    return requests


def fetch_fred(alias: str, spec: Dict[str, Any], asof: Optional[str] = None,
               timeout: int = 20,
               lookback_months: int = DEFAULT_LOOKBACK_MONTHS) -> Dict[str, Any]:
    key = os.environ.get('FRED_API_KEY', '').strip()
    sid = spec.get('series_id')
    if not key:
        raise MacroError('no_api_key',
                         'FRED_API_KEY 환경변수 미설정 (.env 또는 셸 export)',
                         series_id=sid)
    asof = asof or dt.date.today().isoformat()
    params = {
        'series_id': sid,
        'api_key': key,
        'file_type': 'json',
        'observation_start': shift_months(asof, -lookback_months),
        'observation_end': asof,
    }
    req = _session()
    try:
        r = req.get(FRED_URL, params=params, timeout=timeout)
    except Exception as e:                      # requests 예외 계층 전체
        raise MacroError('network', f'FRED 요청 실패: {e}', series_id=sid)

    body = r.text or ''
    try:
        payload = json.loads(body)
    except ValueError:
        raise MacroError('bad_json',
                         f'FRED 응답 JSON 파싱 실패 (HTTP {r.status_code}, {len(body)}바이트)',
                         series_id=sid, status=r.status_code, length=len(body),
                         head=body[:200])
    # 400 이어도 본문에 error_message 가 있으면 파서가 api_error 로 승격한다
    if r.status_code != 200 and not isinstance(payload, dict):
        raise MacroError('http_status', f'FRED HTTP {r.status_code}',
                         series_id=sid, status=r.status_code, length=len(body))
    return payload


def fetch_ecos(alias: str, spec: Dict[str, Any], asof: Optional[str] = None,
               timeout: int = 20,
               lookback_months: int = DEFAULT_LOOKBACK_MONTHS) -> Dict[str, Any]:
    key = os.environ.get('BOK_ECOS_API_KEY', '').strip()
    stat = spec.get('stat_code')
    item = spec.get('item_code', '')
    cycle = spec.get('cycle', 'M')
    if not key:
        raise MacroError('no_api_key',
                         'BOK_ECOS_API_KEY 환경변수 미설정 (.env 또는 셸 export)',
                         stat_code=stat)
    asof = asof or dt.date.today().isoformat()
    start = shift_months(asof, -lookback_months)
    if cycle == 'D':
        s, e = start.replace('-', ''), asof.replace('-', '')
    elif cycle == 'M':
        s, e = start[:7].replace('-', ''), asof[:7].replace('-', '')
    elif cycle == 'Q':
        s = f'{start[:4]}Q{(int(start[5:7]) - 1) // 3 + 1}'
        e = f'{asof[:4]}Q{(int(asof[5:7]) - 1) // 3 + 1}'
    else:
        s, e = start[:4], asof[:4]

    url = f'{ECOS_URL}/{key}/json/kr/1/2000/{stat}/{cycle}/{s}/{e}/{item}'
    req = _session()
    try:
        r = req.get(url, timeout=timeout)
    except Exception as e:
        raise MacroError('network', f'ECOS 요청 실패: {e}', stat_code=stat)

    raw = r.content or b''
    if r.status_code != 200:
        raise MacroError('http_status', f'ECOS HTTP {r.status_code}',
                         stat_code=stat, status=r.status_code, length=len(raw))
    try:
        payload = json.loads(raw.decode('utf-8', errors='replace'))
    except ValueError:
        raise MacroError('bad_json',
                         f'ECOS 응답 JSON 파싱 실패 (HTTP {r.status_code}, {len(raw)}바이트)',
                         stat_code=stat, status=r.status_code, length=len(raw),
                         head=raw[:200].decode('utf-8', errors='replace'))
    return payload


def _default_fetch(country: str):
    def _f(alias, spec, **kw):
        src = spec.get('source')
        if src == 'FRED':
            return fetch_fred(alias, spec, **kw)
        if src == 'ECOS':
            return fetch_ecos(alias, spec, **kw)
        raise MacroError('bad_schema', f'알 수 없는 source: {src!r}', alias=alias)
    return _f


def _parse_for(spec: Dict[str, Any], payload: Any) -> List[Tuple[str, float]]:
    if spec.get('source') == 'ECOS':
        return parse_ecos_rows(payload, stat_code=spec.get('stat_code'))
    return parse_fred_observations(payload)


# ============================================================================
# 스냅샷 조립
# ============================================================================
def build_snapshot(country: str, aliases: Optional[Sequence[str]] = None,
                   fetch=None, asof: Optional[str] = None,
                   specs: Optional[Dict[str, Dict[str, Any]]] = None,
                   timeout: int = 20) -> Dict[str, Any]:
    """국가별 매크로 스냅샷. 실패한 지표도 ok=False + error 로 남긴다.

    fetch(alias, spec) -> payload dict  형태로 주입 가능 (테스트/오프라인용).
    """
    country = (country or '').upper()
    if country not in CATALOG:
        raise ValueError(f'지원하지 않는 country: {country!r} (US 또는 KR)')

    table = dict(CATALOG[country])
    if specs:
        table.update(specs)
    aliases = list(aliases) if aliases else list(table)
    unknown = [a for a in aliases if a not in table]
    if unknown:
        raise ValueError(f'{country} 카탈로그에 없는 지표: {unknown} '
                         f'(가능: {sorted(table)})')

    if fetch is None:
        fetch = _default_fetch(country)
        _kw = {'asof': asof, 'timeout': timeout}
    else:
        _kw = {}

    asof = asof or dt.date.today().isoformat()
    snap: Dict[str, Any] = {
        'country': country,
        'asof': asof,
        '_collected_at': dt.datetime.now().isoformat(timespec='seconds'),
        'source': 'FRED (api.stlouisfed.org)' if country == 'US'
                  else 'ECOS 한국은행 경제통계 (ecos.bok.or.kr)',
        'series': {},
        'warnings': [],
        'errors': [],
        # 일부 지표만 조회한 결과인가. True 면 전체 스냅샷 파일을 덮어쓰지 않는다
        # (부분 실행이 전체 스냅샷을 조용히 갈아치우면 다음 리포트가 반쪽 데이터를 본다)
        'subset': set(aliases) != set(CATALOG[country]),
    }

    for alias in aliases:
        spec = table[alias]
        entry: Dict[str, Any] = {
            'alias': alias,
            'label': spec.get('label', alias),
            'unit': spec.get('unit', ''),
            'freq': spec.get('freq', ''),
            'source': spec.get('source', ''),
            'series_id': spec.get('series_id') or spec.get('stat_code'),
            'item_code': spec.get('item_code'),
            'ok': False,
            'warnings': [],
        }
        try:
            payload = fetch(alias, spec, **_kw)
            obs = _parse_for(spec, payload)
            metrics = derive_metrics(obs, spec, asof=asof)
            entry.update(metrics)
            entry['ok'] = True
            ws = sanity_warnings(alias, metrics, spec, asof=asof)
            entry['warnings'] = ws
            for w in ws:
                snap['warnings'].append(f'{alias} ({entry["label"]}): {w}')
        except MacroError as e:
            d = e.as_dict()
            entry['error'] = d
            snap['errors'].append(dict(d, alias=alias))
            snap['warnings'].append(
                f'{alias} ({entry["label"]}) 수집 실패: [{e.reason}] {e.message}')
            LAST_ERRORS.append(dict(d, alias=alias, country=country,
                                    at=snap['_collected_at']))
        except Exception as e:  # 예상 못한 예외도 절대 삼키지 않는다
            d = {'reason': 'unexpected', 'message': f'{type(e).__name__}: {e}'}
            entry['error'] = d
            snap['errors'].append(dict(d, alias=alias))
            snap['warnings'].append(
                f'{alias} ({entry["label"]}) 수집 실패: [unexpected] {type(e).__name__}: {e}')
            LAST_ERRORS.append(dict(d, alias=alias, country=country,
                                    at=snap['_collected_at']))
        snap['series'][alias] = entry

    snap['ok_count'] = sum(1 for s in snap['series'].values() if s['ok'])
    snap['fail_count'] = len(snap['series']) - snap['ok_count']
    snap['ok'] = snap['fail_count'] == 0
    return snap


# ============================================================================
# 출력 (cp949 안전 -- em-dash/이모지 금지, ASCII 괘선만)
# ============================================================================
def _w(s: str) -> int:
    """한글/전각 = 2칸으로 센 표시 폭."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def _pad(s: str, width: int, right: bool = False) -> str:
    gap = max(0, width - _w(s))
    return (' ' * gap + s) if right else (s + ' ' * gap)


def _fmt(v: Optional[float], digits: int = 2) -> str:
    if v is None:
        return '-'
    return f'{v:,.{digits}f}'


def _sfmt(v: Optional[float], digits: int = 2) -> str:
    """부호를 붙인 변화량."""
    if v is None:
        return '-'
    return f'{v:+,.{digits}f}'


def render_table(snap: Dict[str, Any]) -> str:
    cols = [('지표', 44), ('최신값', 14), ('기준일', 12),
            ('3개월', 10), ('12개월', 10), ('출처', 14)]
    lines = []
    title = f"매크로 스냅샷 [{snap['country']}]  asof={snap.get('asof')}  " \
            f"수집={snap.get('_collected_at')}"
    lines.append(title)
    lines.append(f"출처: {snap.get('source', '')}")
    lines.append('')
    lines.append('  '.join(_pad(h, w) for h, w in cols))
    lines.append('-' * (sum(w for _, w in cols) + 2 * (len(cols) - 1)))

    for alias, s in snap['series'].items():
        label = f"{alias} {s.get('label', '')}"
        if not s.get('ok'):
            err = s.get('error') or {}
            lines.append('  '.join([
                _pad(label, cols[0][1]),
                _pad('[FAIL]', cols[1][1]),
                _pad(f"[{err.get('reason', '?')}]",
                     cols[2][1] + cols[3][1] + cols[4][1] + cols[5][1] + 8),
            ]).rstrip())
            lines.append(f"    -> {err.get('message', '')}")
            continue
        unit = s.get('unit', '')
        cu = s.get('change_unit', '')
        lines.append('  '.join([
            _pad(label, cols[0][1]),
            _pad(f"{_fmt(s.get('latest'))}{unit}", cols[1][1], right=True),
            _pad(str(s.get('latest_date') or '-'), cols[2][1], right=True),
            _pad(f"{_sfmt(s.get('change_3m'))}{cu}", cols[3][1], right=True),
            _pad(f"{_sfmt(s.get('change_12m'))}{cu}", cols[4][1], right=True),
            _pad(str(s.get('series_id') or ''), cols[5][1]),
        ]).rstrip())
        if s.get('yoy') is not None:
            lines.append(f"    -> 전년동기비(YoY): {_sfmt(s['yoy'])}%")

    lines.append('')
    lines.append(f"  성공 {snap.get('ok_count')} / 실패 {snap.get('fail_count')}")
    if snap.get('warnings'):
        lines.append('  [WARN]')
        for w in snap['warnings']:
            lines.append(f'    - {w}')
    return '\n'.join(lines)


def save_snapshot(snap: Dict[str, Any], path: Optional[str] = None) -> str:
    if path is None:
        root = Path(__file__).resolve().parent.parent
        suffix = '_subset' if snap.get('subset') else ''
        path = str(root / 'data' / f"_macro_{snap['country']}{suffix}.json")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = f'{path}.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(snap, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, path)
    return path


# ============================================================================
# CLI
# ============================================================================
def resolve_tokens(country: str, tokens: Sequence[str]
                   ) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
    """--series 토큰을 별칭으로 해석. 카탈로그에 없는 FRED 시리즈 ID 도 받아준다."""
    table = CATALOG[country]
    by_id = {}
    for a, sp in table.items():
        for k in ('series_id', 'stat_code'):
            if sp.get(k):
                by_id[str(sp[k]).upper()] = a

    aliases: List[str] = []
    extra: Dict[str, Dict[str, Any]] = {}
    for t in tokens:
        t = t.strip()
        if not t:
            continue
        if t in table:
            aliases.append(t)
        elif t.upper() in by_id:
            aliases.append(by_id[t.upper()])
        elif country == 'US':
            # 카탈로그 밖 FRED 시리즈 -- 단위/이상치 범위를 모르므로 그대로 밝힌다
            extra[t] = {'source': 'FRED', 'series_id': t,
                        'label': f'{t} (카탈로그 외, 단위/범위 미지정)',
                        'unit': '', 'freq': 'D', 'change_mode': 'pct',
                        'sane': (float('-inf'), float('inf'))}
            aliases.append(t)
        else:
            raise SystemExit(
                f'[ERROR] KR 카탈로그에 없는 지표: {t}\n'
                f'        가능: {", ".join(sorted(table))}\n'
                f'        (ECOS 는 통계표/항목 코드 쌍이 필요해 임의 지정이 불가하다. '
                f'KR_SERIES 에 정의를 추가하라.)')
    return aliases, extra


def main(argv: Optional[Sequence[str]] = None) -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

    p = argparse.ArgumentParser(
        description='매크로 실측 시계열 수집 (FRED / 한국은행 ECOS)')
    p.add_argument('country', choices=['US', 'KR', 'us', 'kr'],
                   help='US = FRED, KR = 한국은행 ECOS')
    p.add_argument('--series', default='',
                   help='쉼표 구분 지표 목록 (별칭 또는 FRED 시리즈 ID). 생략 시 전체')
    p.add_argument('--out', default=None, help='출력 JSON 경로 (기본 data/_macro_{국가}.json)')
    p.add_argument('--asof', default=None, help='기준일 YYYY-MM-DD (기본 오늘)')
    p.add_argument('--json', action='store_true', help='표 대신 JSON 을 stdout 으로')
    args = p.parse_args(list(argv) if argv is not None else None)

    country = args.country.upper()
    aliases, extra = (resolve_tokens(country, args.series.split(','))
                      if args.series else (None, None))

    snap = build_snapshot(country, aliases=aliases, specs=extra, asof=args.asof)
    path = save_snapshot(snap, args.out)

    if args.json:
        print(json.dumps(snap, ensure_ascii=False, indent=2, default=str))
    else:
        print(render_table(snap))
        print(f'\n  저장: {path}')

    if snap['errors']:
        print('\n  [수집 실패 진단]', file=sys.stderr)
        for e in snap['errors']:
            print(f"    - {e.get('alias')}: [{e.get('reason')}] {e.get('message')}",
                  file=sys.stderr)
            detail = {k: v for k, v in e.items()
                      if k not in ('alias', 'reason', 'message')}
            if detail:
                print(f'      {json.dumps(detail, ensure_ascii=False, default=str)}',
                      file=sys.stderr)

    if os.environ.get('MACRO_STRICT') == '1' and not snap['ok']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
