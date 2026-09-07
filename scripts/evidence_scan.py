"""
증거 / 반증 스캐너 (v5.5 신설)

출처: 사용자의 `bottleneck-scouting` 스킬(reference/rules.md) 에서 실증된 판정 체계를
우리 리서치 파이프라인으로 옮긴 것. 그 스킬의 실측 결론은 이렇다:

  "반증 수집이 이 워크플로에서 가장 값이 크다. 최종 판정의 대부분을 반증이 결정한다."
  "긍정 논거보다 반증을 먼저 모으는 편이 빠르다."
  "셀사이드 리포트는 구조적 매수 편향이 있어, 긍정 논거만 모으면 전부 병목으로 보인다."

우리 리포트도 같은 병에 걸린다. DART 사업보고서(회사 자기 서술)와 증권사 리포트
(셀사이드)만 읽으면 강세 논거만 쌓인다. v5.2 Self-Attack 은 작성자가 직접 쓰므로
자기 일관성 편향에 그대로 노출된다.

이 스크립트는 **결정론적으로** 원문에서 두 종류를 뽑는다:
  1. 실측 증거 (수치가 붙은 것만) -- 기대/전망/목표치는 증거로 치지 않는다
  2. 반증 (해소됐다 / 여유 있다 / 증설로 풀린다 / 충분하다 / 아직 양산 전)
  3. 실격 신호 (여유 캐파 / 증설 일정 공표 / 판가 협상 열위 / 노출도 희석)

판정은 사람(에이전트)이 한다. 이 스크립트는 **원문 인용과 위치만** 제공한다.
인용은 전부 원문 그대로이고 파일:라인 이 붙으므로 가짜 인용(v4.18 한화에어로 사고)이
구조적으로 불가능하다.

사용법
------
    python scripts/evidence_scan.py 한국콜마
    python scripts/evidence_scan.py OCI홀딩스 --min-quote 2

출력: data/{종목}/_evidence_scan.json + 콘솔 표
"""
import sys
import io
import os
import re
import json
import glob
from datetime import datetime

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 수치 동반 여부 판정용 (증거는 수치가 있어야 인정)
NUM = r'\d'

# --- 1. 실측 증거 유형 (bottleneck-scouting reference/rules.md 의 10종) ---
EVIDENCE = {
    '리드타임': r'리드\s?타임|납기\s*(?:지연|연장|장기화)|delivery\s+lead',
    # 가동률은 실제 퍼센트가 붙어야 증거다 ('가동률' 단어만으로는 표 헤더에 걸린다)
    '가동률': r'가동률[^.\n]{0,40}?\d{2,3}(?:\.\d+)?\s*%|풀\s?캐파|full\s+capacity',
    '수주잔고': r'수주\s?잔고|수주잔액|backlog|수주\s*총액',
    'BB비율': r'B/?B\s*(?:ratio|비율)|book[- ]to[- ]bill',
    '판가상승': r'판가\s*(?:인상|상승|전가)|가격\s*(?:인상|인상분\s*전가)|ASP\s*(?:상승|인상)',
    '재고소진': r'재고\s*(?:소진|고갈|부족)|품절|재고\s*수준\s*(?:최저|하락)',
    '수요초과': r'수요가?\s*공급(?:을|를)?\s*(?:초과|상회|넘어)|공급\s*부족|수급\s*(?:타이트|핍박)',
    '증설시간': r'증설.{0,20}(?:소요|걸린|필요)|양산.{0,10}(?:20\d{2}년|\d+년\s*후)',
    '규제장벽': r'인증.{0,15}(?:필요|취득|소요)|허가.{0,10}(?:지연|장기)|규제\s*장벽',
    '단일공급': r'유일(?:한)?\s*(?:공급|생산|업체)|독점\s*공급|단독\s*(?:공급|벤더)|소수\s*업체',
}

# --- 2. 반증 유형 (가장 중요) ---
COUNTER = {
    '병목해소': r'병목.{0,12}(?:해소|완화|풀렸|정상화)|공급\s*(?:정상화|안정화|회복)',
    '여유캐파': r'여유\s*(?:캐파|생산능력|CAPA)|가동률.{0,8}(?:하락|저조|미달)|유휴\s*(?:설비|캐파)',
    '증설로해소': r'증설.{0,15}(?:완료|가동|해소|공급\s*확대)|신규\s*(?:라인|공장).{0,12}가동',
    '공급충분': r'공급(?:이|은)?\s*(?:충분|원활|안정화)|공급\s*과잉|물량\s*(?:여유|초과)|수급\s*(?:완화|안정)',
    # '개발 단계' 단독은 회계 주석에 흔하다. 제품/양산 맥락을 요구한다.
    '양산전': r'양산\s*(?:이|은)?\s*(?:아직|전|미개시)|시제품|아직.{0,12}판매되지|(?:제품|신제품|신규\s*라인).{0,20}개발\s*단계',
    '판가열위': r'판가\s*(?:협상|인하|하락|압박)|가격\s*(?:경쟁|인하\s*압력|하락)',
    '수요둔화': r'수요\s*(?:둔화|감소|부진|약세)|전방\s*(?:부진|둔화)|주문\s*(?:감소|취소)',
}

# --- 3. 실격 신호 (bottleneck-scouting 실격 조건 5가지) ---
DISQUALIFY = {
    '해소일정공표': r'(?:20\d{2})년\s*(?:부터)?\s*(?:증설|신규\s*라인|양산)\s*(?:완료|가동|개시)',
    '점유율만': r'점유율\s*\d+(?:\.\d+)?%',
    '노출도희석': r'매출\s*(?:비중|비율)\s*[:은는]?\s*[0-4](?:\.\d+)?%',
}

# 전망성 표현 -- 이게 붙어 있으면 실측 증거가 아니라 전망이다
FORECAST = re.compile(
    r'전망|예상|기대|추정|가이던스|목표(?:치|주가)?|계획|~할\s*것|것으로\s*보|CAGR|전월비\s*전망')

CTX = 130          # 인용 앞뒤 글자수

# 재무제표 주석 / 회계정책 구간은 사업 실체와 무관한 보일러플레이트다.
# 실측: 씨에스윈드 1차 스캔에서 '양산전' 히트 2건이 전부 무형자산 개발비 인식 정책이었다.
BOILERPLATE = re.compile(
    r'감가상각|무형자산|회계정책|공정가치|충당부채|리스부채|이연법인세|'
    r'금융상품|손상차손\s*인식|주석\s*\d|연결재무제표\s*주석|재무제표\s*작성\s*기준|'
    r'내부적으로\s*창출|연구활동에\s*대한\s*지출|비용으로\s*인식')

# 숫자가 있어도 표 조각이면 인용 가치가 없다 (숫자 나열 비중이 과도한 경우).
def _is_table_fragment(quote):
    digits = sum(c.isdigit() for c in quote)
    return digits / max(len(quote), 1) > 0.28


def iter_source_files(stock):
    """정독 대상 원문 파일. DART 전문 > 브로커 리포트 > 임시 덤프 순."""
    d = f'data/{stock}'
    pats = [
        (f'{d}/_dart_FULL_*.txt', 'DART'),
        (f'{d}/reports_text/*.txt', '증권사'),
        (f'{d}/_tmp_*.txt', 'DART덤프'),
        (f'{d}/_sec_*.txt', 'SEC'),
    ]
    for pat, kind in pats:
        for p in sorted(glob.glob(pat)):
            yield p, kind


def scan_text(text, patterns, want_number=True):
    """패턴별 히트를 (유형, 인용, 라인번호, 수치포함, 전망성) 로 반환."""
    hits = []
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == '\n':
            line_starts.append(i + 1)

    def lineno(pos):
        lo, hi = 0, len(line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if line_starts[mid] <= pos:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    for label, pat in patterns.items():
        for m in re.finditer(pat, text, re.I):
            s = max(0, m.start() - CTX)
            e = min(len(text), m.end() + CTX)
            quote = re.sub(r'\s+', ' ', text[s:e]).strip()
            has_num = bool(re.search(NUM, quote))
            is_fc = bool(FORECAST.search(quote))
            if want_number and not has_num:
                continue
            if BOILERPLATE.search(quote):
                continue
            if _is_table_fragment(quote):
                continue
            hits.append({
                'type': label, 'quote': quote, 'line': lineno(m.start()),
                'has_number': has_num, 'forecast_only': is_fc and not re.search(
                    r'\d+(?:\.\d+)?\s*(?:%|배|억|조|개월|년|일|톤|달러|원)', quote),
            })
    return hits


def dedupe(hits, limit_per_type=4):
    """같은 유형 안에서 유사 인용을 줄인다 (앞 60자 기준)."""
    seen, out, per_type = set(), [], {}
    for h in hits:
        key = (h['type'], h['quote'][:60])
        if key in seen:
            continue
        seen.add(key)
        n = per_type.get(h['type'], 0)
        if n >= limit_per_type:
            continue
        per_type[h['type']] = n + 1
        out.append(h)
    return out


def main(stock, min_quote=1):
    files = list(iter_source_files(stock))
    if not files:
        print(f"[ERR] data/{stock}/ 에 정독 대상 원문이 없다.")
        print("  DART 전문(_dart_FULL_*.txt) 또는 "
              "증권사 리포트(reports_text/*.txt)를 먼저 수집할 것.")
        print("  python scripts/fetch_broker_reports.py {종목}")
        return 1

    result = {
        '_description': f'{stock} 증거/반증 스캔 (결정론적, LLM 미개입)',
        '_scanned_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'stock': stock,
        'files': [],
        'evidence': [], 'counter': [], 'disqualify': [],
    }

    total_chars = 0
    for path, kind in files:
        try:
            text = open(path, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        total_chars += len(text)
        result['files'].append({'path': path, 'kind': kind, 'chars': len(text)})
        rel = os.path.basename(path)
        for bucket, pats, want_num in (
                ('evidence', EVIDENCE, True),
                ('counter', COUNTER, False),
                ('disqualify', DISQUALIFY, True)):
            for h in scan_text(text, pats, want_number=want_num):
                h['file'] = rel
                h['source'] = kind
                result[bucket].append(h)

    for bucket in ('evidence', 'counter', 'disqualify'):
        result[bucket] = dedupe(result[bucket])

    ev_real = [h for h in result['evidence'] if not h['forecast_only']]
    ev_fc = [h for h in result['evidence'] if h['forecast_only']]

    print(f"\n{'=' * 72}")
    print(f"  증거/반증 스캔: {stock}")
    print(f"{'=' * 72}")
    print(f"  원문 {len(files)}개 / {total_chars:,}자")
    print(f"\n  실측 증거 {len(ev_real)}건 / 전망성(증거 아님) {len(ev_fc)}건 "
          f"/ **반증 {len(result['counter'])}건** / 실격신호 {len(result['disqualify'])}건")

    def show(title, hits, n=3):
        if not hits:
            print(f"\n  [{title}] 없음")
            return
        print(f"\n  [{title}] {len(hits)}건")
        by_type = {}
        for h in hits:
            by_type.setdefault(h['type'], []).append(h)
        for t, hs in by_type.items():
            print(f"    - {t} ({len(hs)}건)  예: {hs[0]['file']}:{hs[0]['line']}")
            for h in hs[:n if t else 1][:1]:
                print(f"        \"{h['quote'][:150]}\"")

    show('실측 증거', ev_real)
    show('반증 -- 가장 중요', result['counter'])
    show('실격 신호', result['disqualify'])

    if not result['counter']:
        print("\n  [WARN] 반증 0건. 원문에 정말 없는 것인지, 패턴이 안 걸린 것인지")
        print("         직접 확인할 것. 셀사이드/회사 자기서술만 읽으면 강세 논거만 쌓인다.")
    if len(ev_fc) > len(ev_real):
        print(f"\n  [WARN] 전망성 표현({len(ev_fc)})이 실측({len(ev_real)})보다 많다.")
        print("         '전망/기대/목표치는 증거가 아니다' -- 투자포인트를 전망으로만 채우지 말 것.")

    os.makedirs(f'data/{stock}', exist_ok=True)
    path = f'data/{stock}/_evidence_scan.json'
    json.dump(result, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n[OK] saved: {path}")
    print("  인용은 전부 원문 그대로이고 file:line 이 붙어 있다.")
    print("  리포트 인용 박스는 반드시 이 파일의 quote 를 복사할 것 (v4.18 가짜 인용 차단).")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python scripts/evidence_scan.py {종목명}")
        sys.exit(1)
    mq = 1
    if '--min-quote' in sys.argv:
        mq = int(sys.argv[sys.argv.index('--min-quote') + 1])
    sys.exit(main(sys.argv[1], mq))
