"""report_charts.py -- /research PDF 리포트에 도표를 심는다.

배경(2026-09 위닝펀드 수상작 14편 실측): 도표를 실은 8편은 **페이지당 1.0~1.6개**를
싣는다. 한 페이지 = 소제목 하나 + 산문 1,000~1,500자 + 도표 한 장이 표준이다.
같은 종목 우리 리포트의 도표는 **0개**였다 -- `generate_all.py` 에 이미지 삽입
기능 자체가 없었다. 도표 라이브러리(`wf_charts.py` 13종)와 계획기
(`wf_chart_planner.py`)는 이미 있었고 Word 경로에만 연결돼 있었다.

동작: analysis.json -> 도표 계획 -> PNG 렌더 -> base64 인라인 figure.
마크다운에 `[[CHART:n]]` 토큰을 심고 **HTML 변환 후에** 치환한다.
마크다운 단계에서 raw HTML 을 넣으면 파서가 <p> 로 감싸거나 삼킨다.

import 전용. 직접 실행하면 지정 종목의 도표를 렌더해 개수만 보고한다.
"""
import base64
import io
import json
import os
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

CHART_TOKEN_RE = re.compile(r'\[\[CHART:(\d+)\]\]')
_HEADING_RE = re.compile(r'^\s*#{3,4}\s+', re.M)


def number_charts(charts, order):
    """섹션 렌더 순서대로 도표 번호를 1부터 매긴다.

    order 에 없는 섹션의 도표는 **버리지 않고 뒤에 붙인다.** 조용히 사라지면
    본문이 참조하는 도표가 없어지고 아무도 모른다.
    """
    rank = {k: i for i, k in enumerate(order or [])}
    tail = len(rank)
    ordered = sorted(range(len(charts)),
                     key=lambda i: (rank.get(charts[i].get('section_key'), tail), i))
    out = []
    for n, i in enumerate(ordered, start=1):
        c = dict(charts[i])
        c['n'] = n
        out.append(c)
    return out


# v5.9 6섹션 구조에서 호스트로 병합되는 섹션 (CLAUDE.md 병합표와 동일)
HOST_MAP = {
    's05_management_fieldcheck': 's03_company_overview',
    's08_esg': 's09_scenarios_risks',
    's10_earnings_consensus': 's02_thesis_catalysts',
    's11_supply_shareholder': 's02_thesis_catalysts',
    's12_action_plan': 's07_valuation',
}


def remap_to_hosts(charts, sections):
    """병합돼 비어 있는 섹션의 도표를 호스트 섹션으로 옮긴다.

    실측(와이지엔터 v7): 도표 8개 중 3개가 s10/s11/s12 를 가리켰는데 그 섹션들은
    호스트로 병합돼 본문이 ''다. 재매핑하지 않으면 그 도표가 조용히 사라진다.

    본문이 남아 있는 섹션(구 12섹션 리포트)은 건드리지 않는다.
    호스트마저 비어 있으면 옮기지 않는다 -- 갈 곳이 없다.
    """
    out = []
    for c in charts:
        c = dict(c)
        k = c.get('section_key')
        host = HOST_MAP.get(k)
        if host and not (sections.get(k) or '').strip() and (sections.get(host) or '').strip():
            c['section_key'] = host
        out.append(c)
    return out


def distribute_charts(section_md, count):
    """도표 count 개를 소제목 블록에 분배 -> 도표별 블록 인덱스 목록.

    블록보다 도표가 많으면 마지막 블록에 몰아 넣는다. 블록보다 적으면
    앞 블록부터 하나씩. 소제목이 없으면 전부 0번(본문 끝).
    """
    if count <= 0:
        return []
    blocks = max(1, len(_HEADING_RE.findall(section_md or '')))
    return [min(i, blocks - 1) for i in range(count)]


def inject_tokens(section_md, charts):
    """소제목 블록 끝에 `[[CHART:n]]` 토큰을 심는다. 토큰은 자기 줄에 단독으로 둔다."""
    if not charts:
        return section_md
    text = section_md or ''
    slots = distribute_charts(text, len(charts))

    # 소제목 위치로 블록 경계를 만든다 (블록 i 의 끝 = 블록 i+1 의 시작 직전)
    starts = [m.start() for m in _HEADING_RE.finditer(text)]
    if not starts:
        bounds = [len(text)]
    else:
        bounds = starts[1:] + [len(text)]

    # 뒤에서부터 삽입해야 앞쪽 오프셋이 밀리지 않는다
    inserts = []
    for c, blk in zip(charts, slots):
        inserts.append((bounds[blk], c['n']))
    out = text
    for pos, n in sorted(inserts, key=lambda x: -x[0]):
        head, tail = out[:pos], out[pos:]
        if head and not head.endswith('\n'):
            head += '\n'
        out = head + f'\n[[CHART:{n}]]\n\n' + tail
    return out


# 데이터가 있다고 그리던 관성 도표. 어떤 주장도 증명하지 않으므로 PDF 에는 싣지 않는다.
# (Word 경로 /wf-report 는 자체 계획을 쓰므로 영향 없다.)
WEAK_TITLES = ('EPS 5년 추이', 'ROE 5년 추이', '순현금 5년 추이')


def drop_weak(charts):
    """논거와 연결되지 않는 도표를 뺀다. 반환: (남긴 것, 뺀 제목 목록)"""
    keep, dropped = [], []
    for c in charts:
        t = (c.get('title') or '')
        if any(w in t for w in WEAK_TITLES) and not (c.get('claim') or '').strip():
            dropped.append(t)
        else:
            keep.append(c)
    return keep, dropped


def _num(x):
    """'1,731' / '-186' / 1731 -> float. 숫자가 아니면 None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    t = str(x).replace(',', '').replace('%', '').strip()
    t = t.replace('−', '-')
    if t in ('', '-', '--', 'N/A', '적자'):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def caption_of(chart):
    """'도표 N. 주장 -- 제목'. 주장이 없으면 제목만.

    수상작 캡션은 "도표 11. K-POP 4사 두 문제 동시 해결 비교" 처럼 **무엇을 그렸는지**만
    말한다. 캡션이 결론을 말하면 도표가 주장의 증거가 된다 -- 수상작을 넘어서는 지점.
    """
    claim = (chart.get('claim') or '').strip()
    title = (chart.get('title') or '').strip()
    body = f'{claim} -- {title}' if claim and title else (claim or title)
    return f'도표 {chart["n"]}. {body}'


def _q_row(quarterly, *names):
    """분기표에서 이름이 일치하는 행 -> (분기 라벨, 값 리스트)."""
    q = quarterly or {}
    heads = [str(h) for h in (q.get('headers') or [])][1:]
    for row in (q.get('rows') or []):
        label = str(row[0]) if row else ''
        if any(n in label for n in names):
            return heads, [_num(v) for v in row[1:]]
    return None, None


def claim_charts(A):
    """**논거를 증명하는** 도표만 만든다. 데이터가 없으면 만들지 않는다.

    데이터가 있다고 그리면 "EPS 5년 추이" 처럼 어떤 주장도 뒷받침하지 않는
    도표가 늘어난다. 도표 수를 수상작에 맞추는 것은 목표가 아니다.
    """
    out = []
    A = A or {}
    price = A.get('price') or {}
    quarters, ctrl = _q_row(A.get('quarterly'), '지배주주 순이익', '지배순이익')

    # 1) 컨센서스가 요구하는 하반기 -- 확정 실적과 나란히 놓는다
    # 라벨이 데이터와 어긋나면 수치 오류보다 나쁘다 -- 독자가 검증할 수 없다.
    # v5.9 이후 forward_eps 에 **자체 추정**을 넣는 관행이 생겼으므로
    # consensus_eps 가 따로 있을 때만 '컨센서스' 라고 부른다.
    ce = _num(price.get('consensus_eps'))
    fe = ce if ce else _num(price.get('forward_eps'))
    is_consensus = bool(ce)
    sh = _num(price.get('shares_outstanding'))
    if fe and sh and quarters and ctrl and len([v for v in ctrl if v is not None]) >= 4:
        need_year = fe * sh / 1e8            # 억원
        # 분기표 길이가 4가 아닐 수 있다 -- 값이 있는 **마지막 4개 분기**를 쓴다
        avail = [v for v in ctrl if v is not None][-4:]
        h1 = sum(avail[-2:])
        prev_h2 = sum(avail[:2])
        need_h2 = need_year - h1
        if need_h2 > 0 and h1 > 0:
            out.append({
                'kind': 'consensus_requirement',
                'section_key': 's02_thesis_catalysts',
                'archetype': 'consensus_gap',
                'title': ('지배주주 순이익 -- 확정 실적 vs 컨센서스 요구치'
                          if is_consensus else
                          '지배주주 순이익 -- 확정 실적 vs 본 리포트 추정 요구치'),
                'claim': (f'컨센서스는 하반기에 상반기의 {need_h2 / h1:.2f}배를 요구한다'
                          if is_consensus else
                          f'본 리포트 추정도 하반기에 상반기의 {need_h2 / h1:.2f}배를 요구한다'),
                'source': ('분기 실측(DART) + 컨센서스 EPS x 발행주식수' if is_consensus
                           else '분기 실측(DART) + 본 리포트 추정 EPS x 발행주식수'),
                'data': {'categories': ['전년 하반기', '올 상반기(확정)',
                                        '올 하반기(컨센 요구)' if is_consensus
                                        else '올 하반기(추정 요구)'],
                         'series': {'지배주주 순이익(억원)':
                                    [round(prev_h2), round(h1), round(need_h2)]},
                         'ylabel': '지배주주 순이익 (억원)'},
            })

    # 2) 지배 비율 추이 -- 연결 이익이 주주에게 얼마나 도착하는가
    _, cons = _q_row(A.get('quarterly'), '연결 순이익', '순이익')
    if quarters and ctrl and cons and len(ctrl) == len(cons):
        ratios, cats = [], []
        for q, c, n in zip(quarters, ctrl, cons):
            if c is None or not n:
                continue
            ratios.append(round(c / n * 100, 1))
            cats.append(q)
        if len(ratios) >= 3:
            lo = min(ratios)
            out.append({
                'kind': 'controlling_ratio',
                'section_key': 's03_company_overview',
                'archetype': 'consensus_gap',
                'title': '연결 순이익 대비 지배주주 몫',
                'claim': f'주주 몫이 최저 {lo:.1f}%까지 내려왔다',
                'source': '분기 실측(DART)',
                'data': {'categories': cats,
                         'series': {'지배 비율(%)': ratios}, 'ylabel': '지배 비율 (%)'},
            })
    return out


def figure_html(chart):
    """base64 PNG + '도표 N. 제목' 캡션 + 출처선. 수상작 표기 규칙을 따른다."""
    b64 = chart.get('b64')
    if not b64:
        return ''
    title = chart.get('title') or ''
    src = (chart.get('source') or '').strip()
    src_html = f'<div class="chart-source">자료: {src}</div>' if src else ''
    return (
        '<figure class="report-chart">'
        f'<img src="data:image/png;base64,{b64}" alt="{title}">'
        f'<figcaption>{caption_of(chart)}</figcaption>'
        f'{src_html}</figure>'
    )


def replace_tokens(html, charts):
    """HTML 안의 토큰을 figure 로 치환. 렌더 실패·미계획 토큰은 **제거**한다.

    토큰만 들어 있던 <p> 껍데기도 함께 지운다 -- 빈 문단이 페이지 밀림을 만든다.
    """
    by_n = {c['n']: c for c in charts}

    def sub(m):
        c = by_n.get(int(m.group(1)))
        return figure_html(c) if c else ''

    out = re.sub(r'<p>\s*\[\[CHART:(\d+)\]\]\s*</p>',
                 lambda m: sub(m), html)
    out = CHART_TOKEN_RE.sub(sub, out)
    out = re.sub(r'<p>\s*</p>', '', out)
    return out


# ---------------------------------------------------------------- 렌더
def build_charts(analysis_path, out_dir, section_order=None, sections=None):
    """analysis.json -> 렌더된 도표 목록. 실패는 삼키지 않고 이유를 함께 돌려준다.

    반환: (charts, problems)
      charts   = [{'n','section_key','title','source','b64','path'}, ...]
      problems = ['archetype=xxx 렌더 실패: ...', ...]
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    problems = []
    try:
        from wf_chart_planner import plan as _plan
        import wf_charts
    except Exception as e:
        return [], [f'도표 모듈 import 실패: {type(e).__name__}: {e}']

    try:
        planned = _plan(analysis_path)
    except Exception as e:
        return [], [f'도표 계획 실패: {type(e).__name__}: {e}']

    # plan() 은 (chart_plan.json 경로, entries) 를 돌려준다
    entries = planned[1] if isinstance(planned, tuple) else (planned.get('charts') or [])
    items = [c for c in entries if c.get('data')]

    # 논거를 증명하는 도표를 추가하고, 관성 도표는 뺀다
    try:
        with open(analysis_path, encoding='utf-8') as _f:
            _A = json.load(_f)
        items = items + claim_charts(_A)
    except Exception as e:
        problems.append(f'논거 도표 생성 실패: {type(e).__name__}: {e}')
    items, _dropped = drop_weak(items)
    for _t in _dropped:
        problems.append(f"도표 '{_t}' 제외 -- 논거와 연결되지 않는다")
    if sections is not None:
        items = remap_to_hosts(items, sections)
        # 호스트가 없어 본문이 빈 섹션에 남은 도표는 실을 자리가 없다 -- 이유를 남긴다
        keep = []
        for c in items:
            if (sections.get(c.get('section_key')) or '').strip():
                keep.append(c)
            else:
                problems.append(
                    f"도표 '{c.get('title')}' -- 섹션 {c.get('section_key')} 이 비어 있어 제외")
        items = keep
    items = number_charts(items, section_order or [])

    os.makedirs(out_dir, exist_ok=True)
    out = []
    for c in items:
        arche = c.get('archetype')
        try:
            path = wf_charts.render(arche, c.get('data'), None, out_dir, f'chart_{c["n"]:02d}')
        except Exception as e:
            problems.append(f'도표 {c["n"]}({arche}) 렌더 실패: {type(e).__name__}: {e}')
            continue
        if not path or not os.path.exists(path):
            problems.append(f'도표 {c["n"]}: 알 수 없는 아키타입 {arche}')
            continue
        with open(path, 'rb') as f:
            c['b64'] = base64.b64encode(f.read()).decode('ascii')
        c['path'] = path
        out.append(c)
    return out, problems


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    name = sys.argv[1]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = os.path.join(root, 'scripts', f'analysis_{name}.json')
    charts, probs = build_charts(ap, os.path.join(root, 'output', name, 'charts'))
    print(f'[OK] 도표 {len(charts)}개 렌더')
    for c in charts:
        print(f'   도표 {c["n"]:2}. [{c["section_key"]}] {c["title"]}')
    for p in probs:
        print(f'   [WARN] {p}')
