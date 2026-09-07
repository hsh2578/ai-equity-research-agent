"""wf_chart_planner.py -- analysis.json -> data/{종목}/chart_plan.json (하이브리드 도표 매핑).

설계:
- 섹션별 카탈로그 기본 매핑(SECTION_DEFAULTS): 각 정규 섹션 키 -> [(archetype, data_builder)].
- data_builder(A) 는 analysis.json 구조화 필드(financials/price/peers/segments/quarterly/catalysts/supply/opinion)
  에서 도표 data dict 을 만든다. 데이터 없으면 None -> 도표 생략(억지 생성 안 함, 품질 우선).
- 콘텐츠 신호(CONTENT_SIGNALS): 각 섹션 본문/소제목(### ####)을 정규식 스캔해 특수 도표를 추가 제안.
  데이터가 구조화 필드에 없는 특수 도표(risk_matrix/waterfall 등)는 data=null 인 "제안" 항목으로 남겨
  스킬(LLM)이 본문 근거로 채우게 한다. CLI 단독 실행(테스트)에서는 data=null 항목은 렌더 시 생략된다.

출력 chart_plan.json 항목: {order, section_key, archetype, title, source, name, data}
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path

DEFAULT_AUTHOR = '위닝펀드 3조 황성혁'

# 정규 12 섹션 키
CANON = ['s01_opinion_thesis', 's02_thesis_catalysts', 's03_company_overview',
         's04_industry_competition', 's05_management_fieldcheck', 's06_financial',
         's07_valuation', 's08_esg', 's09_scenarios_risks', 's10_earnings_consensus',
         's11_supply_shareholder', 's12_action_plan']


def _num(x):
    """숫자 또는 '194(발표기준)' 같은 문자열에서 첫 숫자 추출. 실패 시 None."""
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        m = re.search(r'-?\d[\d,]*\.?\d*', x.replace(',', ''))
        if m:
            try:
                return float(m.group())
            except ValueError:
                return None
    return None


def _fin_row(A, *substrs, require_all=None):
    """financials.rows 에서 키에 substrs 가 (모두/하나) 포함된 첫 행 -> (years, vals)."""
    fin = A.get('financials', {})
    headers = fin.get('headers', [])
    years = headers[1:]
    for k, v in fin.get('rows', {}).items():
        ok = all(s in k for s in substrs) if require_all else any(s in k for s in substrs)
        if ok:
            return years, [_num(x) for x in v]
    return None, None


def _short_name(name):
    return re.sub(r'\s*\(.*?\)\s*', '', name).strip()


# === data builders (analysis -> data dict | None) ===
def b_segment_pie(A):
    segs = A.get('segments') or []
    if not segs:
        return None
    return {'labels': [s['name'] for s in segs], 'values': [s.get('pct', 0) for s in segs]}


def b_peer_multiples(A):
    peers = A.get('peers') or []
    if len(peers) < 2:
        return None
    names, per, pbr, hl = [], [], [], 0
    sname = A.get('meta', {}).get('stock_name', '')
    for i, p in enumerate(peers):
        nm = _short_name(p.get('name', ''))
        names.append(nm.replace('테인먼트', '').replace('엔터', 'YG') if sname.startswith(nm[:2]) else nm)
        per.append(_num(p.get('per')))
        pbr.append(_num(p.get('pbr')))
        if p.get('highlight') or '본 종목' in p.get('name', '') or sname[:3] in p.get('name', ''):
            hl = i
    return {'names': names, 'per': per, 'pbr': pbr, 'highlight_idx': hl}


def b_dupont_roe(A):
    years, vals = _fin_row(A, 'ROE')
    if not years or all(v is None for v in vals):
        return None
    return {'years': years, 'roe': [v or 0 for v in vals]}


def b_bars_from_row(label_match, ylabel, total=False):
    def _b(A):
        years, vals = _fin_row(A, label_match)
        if not years or all(v is None for v in vals):
            return None
        return {'categories': years, 'series': {ylabel: [v or 0 for v in vals]}, 'ylabel': ylabel}
    return _b


def b_quarterly_revenue(A):
    q = A.get('quarterly', {})
    headers = q.get('headers', [])
    if len(headers) < 2:
        return None
    quarters = headers[1:]
    for k, v in q.get('rows', {}).items():
        if k.startswith('매출'):
            return {'categories': quarters, 'series': {'매출액(억원)': [_num(x) or 0 for x in v]},
                    'ylabel': '매출액 (억원)'}
    return None


def b_catalyst_timeline(A):
    cats = A.get('catalysts') or []
    if not cats:
        return None
    events = []
    for c in cats[:6]:
        events.append({'date': c.get('date', ''), 'label': c.get('event', ''),
                       'impact': (c.get('impact', '') or '')[:42]})
    return {'events': events}


def b_supply_bar(A):
    s = A.get('supply') or {}
    if not any(k in s for k in ('foreign', 'institution', 'individual')):
        return None
    days = s.get('days', 20)
    return {'categories': ['외국인', '기관', '개인'],
            'series': {f'{days}일 순매수(주)': [_num(s.get('foreign')) or 0,
                                              _num(s.get('institution')) or 0,
                                              _num(s.get('individual')) or 0]},
            'ylabel': '순매수 (주)'}


def b_scenario_bar(A):
    op = A.get('opinion') or {}
    vals = [_num(op.get('target_bear')), _num(op.get('target_base')), _num(op.get('target_bull'))]
    if all(v is None for v in vals):
        return None
    return {'categories': ['Bear', 'Base', 'Bull'],
            'series': {'목표주가(원)': [v or 0 for v in vals]}, 'ylabel': '목표주가 (원)'}


# === 섹션별 카탈로그 기본 매핑 ===
# (archetype, builder, 기본 title, source)
SECTION_DEFAULTS = {
    's02_thesis_catalysts': [('event_timeline', b_catalyst_timeline, '하반기 카탈리스트 타임라인', '공시·언론 종합, {author}')],
    's03_company_overview': [('quarterly_composition', b_segment_pie, '{stock} 매출 부문 구성', '사업보고서')],
    's04_industry_competition': [('peer_multiples', b_peer_multiples, '{industry} Peer PER·PBR 비교', 'FnGuide, KIS')],
    's06_financial': [('dupont_roe', b_dupont_roe, 'ROE 5년 추이', 'FnGuide'),
                      ('consensus_gap', b_bars_from_row('순현금', '순현금(억원)'), '순현금 5년 추이', 'FnGuide, 사업보고서')],
    's07_valuation': [('consensus_gap', b_bars_from_row('EPS', 'EPS(원)'), 'EPS 5년 추이 (밸류 기반)', 'FnGuide, {author}')],
    's10_earnings_consensus': [('consensus_gap', b_quarterly_revenue, '분기 매출 추이', 'FnGuide, 분기보고서')],
    's11_supply_shareholder': [('consensus_gap', b_supply_bar, '투자자별 순매수 (최근)', 'KIS API')],
    's12_action_plan': [('consensus_gap', b_scenario_bar, 'Bear/Base/Bull 목표주가', '{author}')],
}

# === 콘텐츠 신호: 본문 키워드 -> 특수 도표 제안 (data 는 스킬이 채움) ===
# (regex, archetype, title, allowed_sections)  -- 적합 섹션에만 부착(요약/개념 언급 섹션 오부착 방지)
CONTENT_SIGNALS = [
    (re.compile(r'리스크\s*매트릭스|확률.{0,6}영향|발생\s*가능성|발생\s*확률'),
     'risk_matrix', '리스크 매트릭스 (확률 x 영향)', {'s09_scenarios_risks'}),
    (re.compile(r'워터폴|분해|덧셈|프리미엄\s*\+|Target\s*PER', re.I),
     'waterfall', '밸류에이션 분해 워터폴', {'s07_valuation'}),
    (re.compile(r'타임라인|로드맵|데뷔\s*일정|컴백\s*일정'),
     'event_timeline', '주요 일정 타임라인', {'s02_thesis_catalysts', 's12_action_plan'}),
    (re.compile(r'분기별\s*활동|동시\s*가동|포트폴리오\s*매트릭스|IP\s*활동'),
     'activity_matrix', '분기별 IP 활동 매트릭스',
     {'s02_thesis_catalysts', 's03_company_overview', 's11_supply_shareholder'}),
    (re.compile(r'순현금\s*(브릿지|bridge|흐름)', re.I),
     'cashflow_bridge', '순현금 Bridge', {'s06_financial', 's07_valuation'}),
    (re.compile(r'경쟁사\s*비교|4사\s*비교|시스템\s*비교|경쟁\s*구도'),
     'fact_comparison', '경쟁사 비교표', {'s04_industry_competition', 's05_management_fieldcheck'}),
]


def _section_text(sections, key):
    """정규 키 우선, 없으면 alias 추정."""
    if key in sections and isinstance(sections[key], str):
        return sections[key]
    return ''


def _subheads(text):
    return [ln.lstrip('#').strip() for ln in text.splitlines() if ln.strip().startswith('###')]


def plan(analysis_path, author=DEFAULT_AUTHOR):
    A = json.load(open(analysis_path, encoding='utf-8'))
    meta = A.get('meta', {})
    stock = meta.get('stock_name', '')
    industry = re.sub(r'\s*\(.*?\)\s*', '', meta.get('industry', '')).strip() or '업종'
    sections = A.get('sections', {})

    def _fmt(s):
        return s.replace('{author}', author).replace('{stock}', stock).replace('{industry}', industry)

    entries = []
    used_per_section = {}
    # 같은 데이터원을 공유해 중복되기 쉬운 아키타입은 리포트 전역 1회만 허용
    SINGLETON = {'event_timeline', 'risk_matrix', 'activity_matrix',
                 'waterfall', 'cashflow_bridge', 'fact_comparison'}
    global_used = set()

    # 1) 카탈로그 기본
    for skey in CANON:
        for arche, builder, title, src in SECTION_DEFAULTS.get(skey, []):
            if arche in SINGLETON and arche in global_used:
                continue
            data = builder(A)
            if data is None:
                continue
            entries.append({'section_key': skey, 'archetype': arche,
                            'title': _fmt(title), 'source': _fmt(src), 'data': data})
            used_per_section.setdefault(skey, set()).add(arche)
            if arche in SINGLETON:
                global_used.add(arche)

    # 2) 콘텐츠 신호 (섹션당 최대 2개 도표 유지)
    for skey in CANON:
        text = _section_text(sections, skey)
        if not text:
            continue
        for rgx, arche, title, allowed in CONTENT_SIGNALS:
            if len(used_per_section.get(skey, set())) >= 2:
                break
            if allowed and skey not in allowed:
                continue
            if arche in used_per_section.get(skey, set()):
                continue
            if arche in SINGLETON and arche in global_used:
                continue
            if rgx.search(text):
                # 구조화 데이터로 만들 수 있는 신호면 즉시 빌드, 아니면 data=null 제안
                data = None
                if arche == 'event_timeline':
                    data = b_catalyst_timeline(A)
                elif arche == 'cashflow_bridge':
                    yrs, vals = _fin_row(A, '순현금')
                    if yrs:
                        data = {'labels': yrs, 'values': [v or 0 for v in vals],
                                'is_total': [True] * len(yrs), 'ylabel': '순현금 (억원)'}
                # risk_matrix / waterfall / activity_matrix / fact_comparison -> data=null (스킬이 채움)
                entries.append({'section_key': skey, 'archetype': arche,
                                'title': title, 'source': author, 'data': data})
                used_per_section.setdefault(skey, set()).add(arche)
                if arche in SINGLETON:
                    global_used.add(arche)

    # 3) 문서 섹션 순서로 정렬 후 번호·이름 부여 (도표 번호 == 문서 등장 순서)
    entries.sort(key=lambda e: CANON.index(e['section_key']))  # stable: 섹션 내 default->signal 순서 유지
    for i, e in enumerate(entries, 1):
        e['order'] = i
        e['caption'] = f'도표 {i}. {e["title"]}'
        e['name'] = f'c{i:02d}_{e["archetype"]}'

    out_dir = Path('data') / stock
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'chart_plan.json'
    json.dump({'stock_name': stock, 'author': author, 'charts': entries},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    return out_path, entries


def main():
    if len(sys.argv) < 2:
        print('usage: python scripts/wf_chart_planner.py {종목명} [analysis_path]')
        sys.exit(1)
    stock = sys.argv[1]
    apath = sys.argv[2] if len(sys.argv) > 2 else f'scripts/analysis_{stock}.json'
    if not Path(apath).exists():
        print(f'[ERROR] analysis 파일 없음: {apath}')
        sys.exit(1)
    out_path, entries = plan(apath)
    ready = sum(1 for e in entries if e['data'] is not None)
    suggested = len(entries) - ready
    print(f'chart_plan 작성: {out_path}')
    print(f'  총 {len(entries)}개 (데이터 준비 {ready} / 제안(스킬이 채움) {suggested})')
    by_sec = {}
    for e in entries:
        by_sec.setdefault(e['section_key'], []).append(e)
    for skey in CANON:
        for e in by_sec.get(skey, []):
            tag = 'OK' if e['data'] is not None else '제안'
            print(f'  [{tag}] {e["caption"]}  <{e["archetype"]}>  (자료: {e["source"]})')


if __name__ == '__main__':
    main()
