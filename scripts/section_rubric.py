"""section_rubric.py -- 애널리스트 리포트 6개 축에 필수 도구가 붙었는지 본다.

배경(2026-09-08 LS일렉트릭 평가): 리포트를 애널리스트 리포트로 놓고 채점하니
**이미 규칙으로 있는 도구가 세 군데서 빠져 있었다.**

  - 밸류에이션: Q1 DCF 가정표 · Q2 민감도표가 규칙인데 배수법만 씀
  - 투자포인트: v5.10 규칙 3 이 요구하는 bottom-up 산식이 서술로만 있음
  - 리스크: 확률·주가영향 정량 매트릭스 없이 서술만

셋 다 **규칙은 있는데 실행되지 않은** 경우다. 프로즈를 한 줄 더 쓰는 것으로는
안 고쳐진다 -- source_coverage 와 같은 이유로 코드가 필요하다.

이 스크립트는 "잘 썼는가"를 재지 않는다. **필수 도구가 붙었는가**만 본다.
문장 품질은 verify_style, 수치는 verify_numbers 가 이미 본다.

등급:
  must -> 없으면 FAIL. 단 **대체 서술이 있으면 통과**시킨다
          (적자기업에 DCF 를 강요하면 안 된다 -- Q5 가 이미 그렇게 정한다)
  want -> 없으면 WARN

사용: python scripts/section_rubric.py {종목명}
"""
import io
import json
import os
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 정규 키 -> (한글 축 이름, [(항목, 정규식, 등급, 대체 인정 정규식 or None)])
RUBRIC = {
    's04_industry_competition': ('산업분석', [
        ('시장 규모·성장률', r'시장\s*규모|CAGR|연평균\s*\d+(?:\.\d+)?%\s*성장', 'must',
         r'시장\s*규모.{0,40}(?:미공시|확인할 수 없|집계.{0,6}없)'),
        ('경쟁 구도', r'동종|경쟁사|Peer|점유율', 'must', None),
        ('정책·규제 환경', r'규제|정책|관세|보조금|법', 'want', None),
        ('전이 사슬(→)', r'→.{0,60}→', 'want', None),
    ]),
    's03_company_overview': ('기업분석', [
        ('사업 구성 표', r'\|\s*부문\s*\||사업\s*구성|매출\s*비중', 'must', None),
        ('지배구조·최대주주', r'최대주주|지배주주|지주회사|최대 주주', 'must', None),
        ('경영진 트랙레코드', r'대표이사|CEO|경영진.{0,20}(?:이력|경력|트랙)', 'want', None),
        ('내부자 매매', r'내부자|임원.{0,10}(?:매수|매도|보유)', 'want', None),
    ]),
    's02_thesis_catalysts': ('투자포인트', [
        # '포인트 1' 이라 안 쓰고 소제목만 두는 리포트가 많다(실측 3/3).
        # 표기가 아니라 **블록 수**로 센다 -- 오탐이 나면 아무도 안 본다.
        ('논거 블록 3개 이상', r'BLOCKS>=3', 'must', None),
        ('bottom-up 산식', r'[×x]\s*\d|산식|÷|나누면|곱하면', 'must', None),
        ('카탈리스트 시점', r'\d{4}년?\s*\d{1,2}월|\dQ\d{2}|분기\s*실적', 'must', None),
        ('컨센 대비 델타', r'컨센서스[^.]{0,50}(?:대비|보다|낮|높|차이)', 'want', None),
    ]),
    's09_scenarios_risks': ('리스크', [
        ('리스크 블록 3개 이상', r'BLOCKS>=3', 'must', None),
        ('확률·영향 정량', r'확률\s*\d+%|시총\s*[-−]\d+%|주가\s*[-−]\d+%', 'must', None),
        ('3단 구조(최대→감경→최종)', r'최대 영향|감경', 'want', None),
        ('자기 논거 공격', r'틀릴|틀린|무너|반박', 'want', None),
    ]),
    's06_financial': ('재무분석', [
        ('현금흐름', r'영업활동현금흐름|영업현금흐름|잉여현금흐름', 'must', None),
        ('수익성 분해(ROE/DuPont)', r'ROE|자기자본이익률|DuPont|듀폰', 'must', None),
        ('안정성 지표', r'부채비율|이자보상|Altman|순차입|순현금|유동비율', 'must', None),
        ('5년 실적 표', r'\|\s*20\d\d\s*\|.*\|\s*20\d\d\s*\|', 'want', None),
    ]),
    's07_valuation': ('밸류에이션', [
        ('DCF 또는 미사용 사유', r'DCF|현금흐름할인|WACC|할인율', 'must',
         r'(?:DCF|현금흐름할인)[^.]{0,60}(?:쓰지 않|부적합|적합하지|의미가 없)'),
        ('민감도 분석', r'민감도|감도\s*분석|시나리오별\s*배수', 'must', None),
        # Peer 표는 sections 밖(analysis.json 의 peers 배열)에서 렌더된다.
        # 섹션 본문만 보면 비교를 해 놓고도 FAIL 이 난다 -> 리포트 전체를 본다.
        ('Peer 상대비교', r'REPORT:동종|Peer|경쟁사|[2-9]사', 'must', None),
        ('3시나리오', r'Bear|Bull', 'must', None),
        ('목표배수 산정 근거', r'Target\s*PER|목표\s*배수|배수를.{0,10}쌓', 'want', None),
    ]),
}

_ALIAS = {'s04_industry_competition': 's04_industry',
          's02_thesis_catalysts': 's02_investment_points',
          's06_financial': 's08_financial',
          's07_valuation': 's09_valuation',
          's09_scenarios_risks': 's10_scenarios_risks'}


def section_text(sections, canon):
    if canon in sections and (sections.get(canon) or '').strip():
        return sections[canon]
    a = _ALIAS.get(canon)
    return (sections.get(a) or '') if a else ''


def _report_text(sections):
    """정규 키 본문 전체. Peer 표처럼 섹션 밖에서 렌더되는 것을 감안한 범위."""
    return '\n'.join(v for v in (sections or {}).values() if isinstance(v, str))


def _hit(pat, section_t, report_t):
    """특수 패턴 둘을 먼저 처리하고 나머지는 평범한 정규식.

    'BLOCKS>=N'  -- 소제목(####) 블록이 N개 이상인가. 표기가 아니라 구조를 센다.
    'REPORT:...' -- 섹션이 아니라 리포트 전체에서 찾는다.
    """
    if pat.startswith('BLOCKS>='):
        return len(re.findall(r'^####\s', section_t, re.M)) >= int(pat.split('>=')[1])
    if pat.startswith('REPORT:'):
        return bool(re.search(pat[len('REPORT:'):], report_t))
    return bool(re.search(pat, section_t))


def grade(sections, rubric=None):
    """반환: [(축, 항목, 상태, 등급)]  상태 = PASS / FAIL / WARN / SKIP"""
    out = []
    report_t = _report_text(sections)
    for canon, (axis, items) in (rubric or RUBRIC).items():
        t = section_text(sections or {}, canon)
        if not t.strip():
            out.append((axis, '(섹션 없음)', 'SKIP', 'must'))
            continue
        for label, pat, level, alt in items:
            if _hit(pat, t, report_t):
                out.append((axis, label, 'PASS', level))
            elif alt and _hit(alt, t, report_t):
                out.append((axis, label, 'PASS', level))   # 안 쓰는 이유를 밝혔다
            else:
                out.append((axis, label, 'FAIL' if level == 'must' else 'WARN', level))
    return out


def main(stock_name):
    p = os.path.join(ROOT, 'scripts', f'analysis_{stock_name}.json')
    if not os.path.exists(p):
        print(f'[ERR] {p} 없음')
        return 2
    sections = (json.load(open(p, encoding='utf-8')).get('sections') or {})
    rows = grade(sections)

    print('=' * 70)
    print(f'  section_rubric (v5.15): {stock_name}')
    print('  애널리스트 6축에 필수 도구가 붙었는가 (문장 품질은 verify_style 이 본다)')
    print('=' * 70)
    icon = {'PASS': '✓', 'FAIL': '✗', 'WARN': '!', 'SKIP': '?'}
    axis_now = None
    fail = warn = 0
    for axis, label, st, _lv in rows:
        if axis != axis_now:
            print(f'\n  [{axis}]')
            axis_now = axis
        fail += st == 'FAIL'
        warn += st == 'WARN'
        print(f'    [{icon[st]}] {label}')
    print()
    print(f'  FAIL {fail}건 / WARN {warn}건')
    if fail:
        print('  [차단] 규칙으로 정해 둔 필수 도구가 빠졌다. '
              '안 쓸 거면 왜 안 쓰는지 본문에 밝혀야 통과한다.')
    return 1 if fail else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
