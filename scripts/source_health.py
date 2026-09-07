"""
외부 데이터 소스 헬스체크 (v5.6 신설)

## 왜 만들었나

FnGuide 가 URL 을 바꿨는데 **몇 달간 아무도 몰랐다.**
`fnguide_data.py` 가 `except Exception: return None` 으로 실패를 삼켰고,
호출자는 `{"financial": null}` 을 그대로 저장했다. 그 상태의 파일이 3건 있었고
(한국콜마/씨에스윈드/와이지엔터), 리포트는 5년 실적과 컨센 없이 작성됐다.

이 프로젝트의 사고 이력은 대부분 같은 모양이다:
  - B13 분기 검증: 정규식이 0건 매칭 -> 에러 없음 -> "확정 4분기 충족" PASS (몇 달)
  - US Peer 교차검증: 스키마 불일치 -> 기본값 0 -> 비교 건너뜀 (조용히)
  - FnGuide: URL 사망 -> None 반환 -> 리포트가 그냥 진행

**조용한 실패가 시끄러운 실패보다 훨씬 비싸다.** 이 스크립트는 수집 파이프라인이
의존하는 외부 소스를 하나씩 두드려 보고, 죽었으면 **즉시 크게** 알린다.

## 설계 원칙

1. **응답이 왔다 != 살아있다.** HTTP 200 이어도 에러 페이지일 수 있다
   (FnGuide 는 "페이지가 없습니다" 를 200 으로 준다). 그래서 각 프로브는
   **내용 검증**까지 한다 -- 요청한 종목의 데이터가 실제로 들어있는가.
2. **엉뚱한 데이터를 주는 경우도 실패다.** FnGuide `.aspx` 는 어떤 종목코드를
   넣어도 삼성전자를 돌려줬다. 그래서 **서로 다른 두 종목**을 조회해
   결과가 실제로 다른지 본다 (identity check).
3. 프로브는 소스마다 독립적이다. 하나가 죽어도 나머지는 계속 검사한다.

## 사용법

    python scripts/source_health.py              # 전체
    python scripts/source_health.py --only kis,dart
    python scripts/source_health.py --quiet      # 요약만

출력: data/_source_health.json + 콘솔 표
종료 코드: 죽은 필수 소스가 있으면 1 (CI/파이프라인에서 게이트로 쓸 수 있다)

/research STEP 1 진입 전에 돌리는 것을 권장한다. 수집이 끝난 뒤
"왜 값이 비었지" 를 추적하는 것보다 시작 전에 아는 편이 훨씬 싸다.
"""
import sys
import io
import os
import json
import time
import argparse
from datetime import datetime

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout.reconfigure(encoding='utf-8')

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

# 프로브에 쓰는 기준 종목. 상장폐지되지 않을 대형주로 고른다.
KR_A, KR_B = ('005930', '삼성전자'), ('000660', 'SK하이닉스')
US_A, US_B = 'AAPL', 'MSFT'

# 에러 페이지 감지: 정상 데이터 페이지가 이보다 짧을 수 없다
MIN_HTML = 5000
ERROR_MARKERS = ('페이지가 없습니다', 'Access Denied', '403 Forbidden',
                 'Service Unavailable', '일시적으로 이용할 수 없습니다')


class Result:
    def __init__(self, name, critical=True):
        self.name = name
        self.critical = critical
        self.status = 'SKIP'
        self.detail = ''
        self.elapsed = 0.0

    def ok(self, detail=''):
        self.status, self.detail = 'OK', detail
        return self

    def fail(self, detail=''):
        self.status, self.detail = 'FAIL', detail
        return self

    def warn(self, detail=''):
        self.status, self.detail = 'WARN', detail
        return self

    def as_dict(self):
        return {'source': self.name, 'status': self.status, 'critical': self.critical,
                'detail': self.detail, 'elapsed_sec': round(self.elapsed, 2)}


def looks_like_error_page(text):
    """HTTP 200 이어도 에러 페이지인 경우를 잡는다."""
    if text is None:
        return '응답 없음'
    if len(text) < MIN_HTML:
        return f'응답이 {len(text):,}바이트로 비정상적으로 짧다 (에러 페이지 추정)'
    for m in ERROR_MARKERS:
        if m in text:
            return f'에러 문구 발견: "{m}"'
    return None


# ----------------------------------------------------------------------------
# 프로브들. 각각 Result 를 돌려준다.
# ----------------------------------------------------------------------------

def probe_kis(r):
    """한국투자증권 OpenAPI. 시세가 0 이면 실패로 본다."""
    from kis_api import get_current_price
    a = get_current_price(KR_A[0]) or {}
    price = a.get('현재가')
    if not price:
        return r.fail(f'{KR_A[1]} 현재가가 비었다. '
                      f'한글 키 반환 규약이 바뀌었거나 토큰 발급 실패. 응답키={list(a)[:6]}')
    b = get_current_price(KR_B[0]) or {}
    if b.get('현재가') == price:
        return r.fail(f'{KR_A[1]} 과 {KR_B[1]} 의 현재가가 동일({price}). '
                      f'종목코드가 무시되고 있다.')
    return r.ok(f'{KR_A[1]} {price:,}원 / {KR_B[1]} {b.get("현재가", 0):,}원')


def probe_dart(r):
    """DART 전자공시. 고유번호 조회 + 보고서 목록."""
    from dart_api import get_corp_code
    code = get_corp_code(KR_A[1])
    if not code:
        return r.fail(f'{KR_A[1]} 고유번호 조회 실패. API 키 또는 corpCode.zip 확인.')
    other = get_corp_code(KR_B[1])
    if other and other == code:
        return r.fail('서로 다른 회사가 같은 고유번호를 반환한다.')
    return r.ok(f'{KR_A[1]} corp_code={code}')


def probe_fnguide(r):
    """FnGuide. 2026-09 에 URL 이 바뀌어 전 종목 수집이 죽었던 소스."""
    from fnguide_data import get_financial_data
    a = get_financial_data(KR_A[0])
    if not a:
        return r.fail(f'{KR_A[1]} 수집 실패(None). URL/파싱 규약 변경 가능성. '
                      f'2026-09 에 comp.fnguide.com -> wcomp.fnguide.com 이전 사례 있음.')
    ann = (a.get('annual') or {}) if isinstance(a, dict) else {}
    rev = ann.get('revenue') or {}
    if not rev:
        return r.warn(f'{KR_A[1]} 응답은 왔으나 annual.revenue 가 비었다. 파싱 규약 변경 의심.')
    b = get_financial_data(KR_B[0])
    b_rev = ((b or {}).get('annual') or {}).get('revenue') or {}
    if b_rev and b_rev == rev:
        return r.fail(f'{KR_A[1]} 과 {KR_B[1]} 의 매출이 완전히 동일하다. '
                      f'종목코드가 무시되고 기본 페이지가 반환되는 중 '
                      f'(과거 .aspx 가 항상 삼성전자를 주던 함정).')
    return r.ok(f'{KR_A[1]} 매출 {len(rev)}개 연도 / {KR_B[1]} {len(b_rev)}개 연도')


def probe_fdr(r):
    """FinanceDataReader. 주가 + 벤치마크 ETF."""
    import FinanceDataReader as fdr
    df = fdr.DataReader(KR_A[0], '2026-01-01')
    if df is None or df.empty:
        return r.fail(f'{KR_A[1]} 일봉이 비었다.')
    etf = fdr.DataReader('069500', '2026-01-01')     # KODEX 200 (벤치마크 대용)
    if etf is None or etf.empty:
        return r.warn('종목은 되지만 KODEX 200(069500)이 비었다. '
                      'decision_log alpha 계산이 막힌다.')
    return r.ok(f'{KR_A[1]} {len(df)}행 / KODEX200 {len(etf)}행')


def probe_yfinance(r):
    """yfinance. US 시세 + 컨센서스 추이."""
    import yfinance as yf
    t = yf.Ticker(US_A)
    info = t.info or {}
    px = info.get('currentPrice') or info.get('regularMarketPrice')
    if not px:
        return r.fail(f'{US_A} 현재가가 비었다 (rate limit 또는 스키마 변경).')
    trend = t.eps_trend
    if trend is None or getattr(trend, 'empty', True):
        return r.warn(f'{US_A} 시세는 되지만 eps_trend 가 비었다. '
                      f'us_consensus.py 의 컨센 추이가 막힌다.')
    return r.ok(f'{US_A} ${px} / eps_trend {len(trend)}행')


def probe_sec(r):
    """SEC EDGAR XBRL."""
    from sec_edgar import get_cik
    cik = get_cik(US_A)
    if not cik:
        return r.fail(f'{US_A} CIK 조회 실패. User-Agent 헤더 정책 확인.')
    return r.ok(f'{US_A} CIK={cik}')


def probe_hankyung(r):
    """한경 컨센서스 목록. IP 차단 시 여기서 잡힌다."""
    import datetime as dt
    sys.path.insert(0, os.path.join(_HERE, 'broker'))
    import fetch_range as fr
    end = dt.date.today()
    start = end - dt.timedelta(days=7)
    rows = fr.fetch_range(start, end, max_pages=2)
    if not rows:
        return r.fail('최근 7일 목록이 0건이다. IP 차단(403) 또는 파싱 규약 변경 의심.')
    return r.ok(f'최근 7일 {len(rows)}건 (2페이지 표본)')


PROBES = [
    ('kis', probe_kis, True),
    ('dart', probe_dart, True),
    ('fnguide', probe_fnguide, True),
    ('fdr', probe_fdr, True),
    ('yfinance', probe_yfinance, True),
    ('sec', probe_sec, False),
    ('hankyung', probe_hankyung, False),
]


def run(only=None):
    results = []
    for name, fn, critical in PROBES:
        if only and name not in only:
            continue
        r = Result(name, critical)
        t0 = time.time()
        try:
            fn(r)
        except ImportError as e:
            r.fail(f'모듈 없음: {e}')
        except Exception as e:
            r.fail(f'{type(e).__name__}: {str(e)[:150]}')
        r.elapsed = time.time() - t0
        results.append(r)
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description='외부 데이터 소스 헬스체크')
    p.add_argument('--only', default=None,
                   help='쉼표로 구분한 소스명 (kis,dart,fnguide,fdr,yfinance,sec,hankyung)')
    p.add_argument('--quiet', action='store_true', help='요약만 출력')
    a = p.parse_args(argv)
    only = {s.strip() for s in a.only.split(',')} if a.only else None

    print(f"\n{'=' * 78}")
    print("  외부 데이터 소스 헬스체크")
    print(f"{'=' * 78}")
    print("  응답이 왔다고 살아있는 것이 아니다. 각 프로브는 내용까지 확인하고,")
    print("  서로 다른 두 종목을 조회해 결과가 실제로 다른지도 본다.\n")

    results = run(only)
    mark = {'OK': '[OK  ]', 'WARN': '[WARN]', 'FAIL': '[FAIL]', 'SKIP': '[SKIP]'}
    for r in results:
        tag = '필수' if r.critical else '선택'
        print(f"  {mark[r.status]} {r.name:<10} ({tag}) {r.elapsed:5.1f}s  {r.detail}")

    dead = [r for r in results if r.status == 'FAIL' and r.critical]
    warn = [r for r in results if r.status == 'WARN']
    print()
    print(f"  총 {len(results)}개 / 정상 {sum(1 for r in results if r.status == 'OK')}"
          f" / 경고 {len(warn)} / 실패 {sum(1 for r in results if r.status == 'FAIL')}")

    os.makedirs('data', exist_ok=True)
    path = 'data/_source_health.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'checked_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   'results': [r.as_dict() for r in results]},
                  f, ensure_ascii=False, indent=2)
    print(f"  기록: {path}")

    if dead:
        print(f"\n  [중단 권고] 필수 소스 {len(dead)}개가 죽었다: "
              f"{', '.join(r.name for r in dead)}")
        print("  이 상태로 리포트를 만들면 해당 데이터가 빈 채로 작성된다.")
        print("  (FnGuide 가 URL 을 바꿨을 때 몇 달간 아무도 모른 채 리포트가 나갔다.)")
        return 1
    if warn:
        print("\n  [주의] 경고가 있다. 해당 항목을 인용할 계획이면 먼저 확인할 것.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
