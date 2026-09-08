"""source_coverage.py -- 1차 출처에 있는데 본문이 안 쓴 것을 찾는다.

배경(2026-09-08 LS일렉트릭 v1): 리포트가 verify_numbers / verify_facts /
preflight 를 **전부 통과하고 verify_style 99점**을 받았는데 결론이 틀렸다.
반증·비평 에이전트가 찾아낸 결정적 근거 셋이 전부 **이미 내려받아 둔
반기보고서 안**에 있었다.

  - 영업활동현금흐름 -819.9억원 (영업이익 3,051억원과 3,871억원 괴리)
  - 부문정보: 전력부문 OPM 8.65% (연결 10.33% 는 연결조정이 만든 착시)
  - 진행기준 계약 주석: 추정변경이 당기 손익 +278억, 미래 손익 -313억

세 가지 모두 손익계산서에는 없다. **기존 검증기는 "쓴 숫자가 맞는가"를 보지
"써야 할 것을 봤는가"를 보지 않는다.** 그 빈자리를 이 스크립트가 메운다.

판정은 단순하다 -- 1차 출처 전문에 그 표/주석이 **있는데** 본문이 한 번도
언급하지 않으면 FAIL. 없으면 SKIP(공시 안 한 회사를 벌하지 않는다).

사용: python scripts/source_coverage.py {종목명}
"""
import glob
import io
import json
import os
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (키, 라벨, 1차출처 정규식, 본문 정규식, 왜 필요한가, 등급)
#   등급 'must'  -> 없으면 FAIL
#   등급 'want'  -> 없으면 WARN (업종에 따라 무의미할 수 있는 것)
PROBES = [
    ('cashflow', '영업활동현금흐름',
     # 서술문("경영진은 영업활동현금흐름과 금융자산의 현금유입으로...")이 아니라
     # **실제 현금흐름표**만 잡는다. 실측: 삼성SDI 는 위험관리 문단에서 걸렸다.
     # 그래서 표 제목이거나, 그 문구 뒤 80자 안에 7자리 이상 숫자가 와야 한다.
     r'현금흐름표|영업활동(?:으로\s*인한)?\s*현금흐름[^\n]{0,80}\(?[\d,]{9,}',
     r'영업활동현금흐름|영업활동 현금흐름|영업현금흐름|잉여현금흐름',
     '이익이 현금으로 돌아오는지는 손익계산서에 없다', 'must'),
    ('segment', '부문정보(연결조정)',
     r'연결조정',
     r'부문정보|연결조정|부문 합계|부문별 영업이익|부문 영업이익률',
     '연결 영업이익률과 사업 실체의 마진은 다를 수 있다', 'must'),
    ('poc', '진행기준 계약 추정변경',
     # '회계추정의 변경' 은 모든 재무제표 주석에 있는 보일러플레이트다.
     # 실측: 와이지엔터 36건 / 삼성SDI 8건이 전부 감가상각 문구였다.
     # 진행기준 계약이 실제로 있는 회사만 잡으려면 표 제목으로 좁혀야 한다.
     r'추정총계약수익의\s*변동',
     r'추정.{0,3}변경|진행기준|원가기준 투입법',
     '수주산업은 추정 변경이 당기 이익을 만든다', 'must'),
    ('backlog', '수주 상황',
     r'수주\s*상황|수주잔고',
     r'수주잔고|수주 잔고',
     '앞으로 인식될 매출이 여기 있다', 'want'),
    ('utilization', '가동률',
     r'평균가동률|가동률',
     r'가동률',
     '팔린 만큼 돌기 때문에 점유율보다 정직하다', 'want'),
    ('price_trend', '제품 가격변동 추이',
     r'제품\s*가격변동\s*추이',
     r'기준가|판가|가격변동|제품 가격',
     '가격 결정력 주장의 유일한 공시 근거다', 'want'),
    ('rnd', '연구개발비용',
     r'연구개발비용',
     r'연구개발',
     '성장이 기술에서 오는지 수요에서 오는지 갈린다', 'want'),
    ('major_holder', '최대주주 지분',
     r'최대주주|주식의\s*분포',
     r'최대주주|지분\s*\d|유통주식',
     '유통물량은 변동성 서술의 근거다', 'want'),
]


def load_source_text(stock_name):
    """DART 전문 덤프를 모두 이어 붙인다. 없으면 요약본이라도."""
    base = os.path.join(ROOT, 'data', stock_name)
    parts = []
    for pat in ('_dart_FULL_*.txt', '_sec_*.txt'):
        for p in sorted(glob.glob(os.path.join(base, pat))):
            try:
                parts.append(open(p, encoding='utf-8').read())
            except OSError:
                pass
    return '\n'.join(parts)


def load_body(stock_name):
    p = os.path.join(ROOT, 'scripts', f'analysis_{stock_name}.json')
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding='utf-8'))
    secs = d.get('sections') or {}
    return '\n'.join(v for v in secs.values() if isinstance(v, str))


def check(source_text, body_text, probes=None):
    """반환: [(키, 라벨, 상태, 사유)]  상태 = PASS / FAIL / WARN / SKIP"""
    out = []
    for key, label, src_pat, body_pat, why, grade in (probes or PROBES):
        in_src = bool(re.search(src_pat, source_text or ''))
        in_body = bool(re.search(body_pat, body_text or ''))
        if not in_src:
            out.append((key, label, 'SKIP', '1차 출처에 없음 (미공시)'))
        elif in_body:
            out.append((key, label, 'PASS', '본문이 인용함'))
        else:
            status = 'FAIL' if grade == 'must' else 'WARN'
            out.append((key, label, status, f'출처에 있는데 본문이 안 씀 -- {why}'))
    return out


def main(stock_name):
    src = load_source_text(stock_name)
    body = load_body(stock_name)
    if body is None:
        print(f'[ERR] scripts/analysis_{stock_name}.json 없음')
        return 2
    if not src:
        print(f'[SKIP] data/{stock_name}/ 에 DART/SEC 전문 덤프가 없다. '
              f'전문을 받아야 이 검증이 의미가 있다.')
        return 0

    print('=' * 70)
    print(f'  source_coverage (v5.14): {stock_name}')
    print(f'  1차 출처 {len(src):,}자 / 본문 {len(body):,}자')
    print('=' * 70)
    rows = check(src, body)
    icon = {'PASS': '✓', 'FAIL': '✗', 'WARN': '!', 'SKIP': '?'}
    fail = warn = 0
    for _, label, status, why in rows:
        fail += status == 'FAIL'
        warn += status == 'WARN'
        print(f'  [{icon[status]}] {label:<22} {status:<5} {why}')
    print()
    print(f'  FAIL {fail}건 / WARN {warn}건')
    if fail:
        print('  [차단] 1차 출처에 있는 것을 본문이 안 썼다. '
              '그 장을 읽고 본문에 반영한 뒤 다시 돌린다.')
    return 1 if fail else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
