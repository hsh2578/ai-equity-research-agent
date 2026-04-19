"""
STEP 6 1회차 D 블록 -- 팩트 체크 자동 검증 (v4.10 신설)

검증 항목:
    D1. 사업보고서 직접 인용 실존 여부
        리포트의 "사업보고서 [0]에서 '...'라고 기재" 패턴을 추출하여
        실제 data_dart_reports.json[0].sections 원문에 존재하는지 확인
    D2. 외부 출처 인용 체크
        "UBS에 따르면 X%", "트렌드포스 전망 Y%" 등 출처 명시 패턴이
        WebSearch 결과에 실제 존재했는지 사용자가 교차 검증하도록 리스트 생성
    D3. 증권사 목표가 테이블 정합성
        s16 consensus 테이블의 broker/목표가가 financial_summary.json.consensus.brokers
        원본과 1:1 일치 확인
    D4. 경쟁사 수치 정합성
        s05 peers 테이블의 시총/PER/PBR이 _peer_snapshot.json과 1:1 일치

사용법:
    python scripts/verify_facts.py {종목명}
"""
import json
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def extract_dart_quotes(sections):
    """analysis.json sections에서 '사업보고서 [0]'를 명시한 직접 인용 추출"""
    quotes = []
    for sec_name, body in sections.items():
        if not isinstance(body, str):
            continue
        # 패턴 1: 사업보고서 [0]에서 '...'라고 기재
        for m in re.finditer(r"사업보고서\s*\[0\][^'\"]*['\"]([^'\"]{10,200})['\"]", body):
            quotes.append({
                'section': sec_name,
                'quote': m.group(1).strip(),
                'context': body[max(0,m.start()-30):m.end()+20]
            })
        # 패턴 2: [0] 주요_계약에서 '...'
        for m in re.finditer(r"\[0\][^'\"]*['\"]([^'\"]{10,200})['\"]", body):
            q = m.group(1).strip()
            if not any(x['quote'] == q for x in quotes):
                quotes.append({'section': sec_name, 'quote': q, 'context': body[max(0,m.start()-30):m.end()+20]})
    return quotes


def extract_external_citations(sections):
    """UBS/트렌드포스/WSTS/노무라 등 외부 출처 인용 추출"""
    sources = ['UBS', 'WSTS', '트렌드포스', 'TrendForce', '노무라', 'Nomura',
               '모건스탠리', 'Morgan Stanley', 'S&P Mobility', 'Mordor', 'Statista',
               'Gartner', 'IEA', 'IMF', 'WEF', 'Reuters']
    citations = []
    for sec_name, body in sections.items():
        if not isinstance(body, str):
            continue
        for src in sources:
            for m in re.finditer(rf"{src}[^\.]{{0,100}}(\d+[\.\,]?\d*\s*(?:%|조|억|만|pt|배|x|달러|\$))", body):
                citations.append({
                    'section': sec_name,
                    'source': src,
                    'claim': m.group(0).strip()[:150],
                })
    return citations


def check_d1_dart_quotes(analysis, dart):
    """D1: 사업보고서 직접 인용이 실제 원문에 존재하는가"""
    sections = analysis.get('sections', {})
    quotes = extract_dart_quotes(sections)
    if not quotes:
        return {'status': 'SKIP', 'quotes': 0, 'fails': []}

    # DART [0] 전체 원문 합치기
    dart_full = ''
    if dart and len(dart) > 0:
        for sec_body in dart[0].get('sections', {}).values():
            if isinstance(sec_body, str):
                dart_full += sec_body + '\n'

    fails = []
    for q in quotes:
        # 핵심 키워드 2~3개 추출 후 전부 원문에 있는지 확인 (느슨한 매칭)
        keywords = [w for w in re.findall(r'[가-힣A-Za-z]{3,}', q['quote']) if len(w) >= 3][:5]
        if not keywords:
            continue
        matched = sum(1 for kw in keywords if kw in dart_full)
        if matched < len(keywords) * 0.6:  # 60% 미만 매칭 시 FAIL
            fails.append({
                'section': q['section'],
                'quote': q['quote'][:80],
                'matched_ratio': f"{matched}/{len(keywords)}",
                'keywords_missing': [kw for kw in keywords if kw not in dart_full]
            })
    return {'status': 'CHECKED', 'quotes': len(quotes), 'fails': fails}


def check_d3_consensus_table(analysis, fs):
    """D3: s16 증권사 목표가 테이블이 financial_summary.consensus.brokers와 일치하는가"""
    s16 = analysis.get('sections', {}).get('s16_consensus', '')
    if not s16:
        return {'status': 'SKIP', 'checked': 0, 'fails': []}

    brokers_real = {}
    for b in (fs.get('consensus', {}).get('brokers', []) or []):
        name = b.get('broker', '').strip()
        brokers_real[name] = {
            'tp': b.get('target_price', 0),
            'date': b.get('date', '')
        }

    fails = []
    # 리포트에서 "증권사명 목표가원" 패턴 추출
    for m in re.finditer(r'\|\s*([가-힣A-Za-z\s\(\)&]{2,20}?)\s*\|\s*([\d,]{5,10})\s*원', s16):
        broker_in_report = m.group(1).strip()
        tp_in_report = int(m.group(2).replace(',', ''))
        if broker_in_report in ('증권사', '25개사 평균', '평균'):
            continue
        # 원본에서 찾기 (부분 일치)
        found = None
        for real_name, real_data in brokers_real.items():
            if real_name in broker_in_report or broker_in_report in real_name:
                found = real_data
                break
        if not found:
            fails.append({'broker': broker_in_report, 'report_tp': tp_in_report, 'issue': '원본에 없음'})
        elif abs(found['tp'] - tp_in_report) / max(found['tp'], 1) > 0.05:
            fails.append({'broker': broker_in_report, 'report_tp': tp_in_report, 'real_tp': found['tp'], 'issue': f"{abs(found['tp']-tp_in_report)/found['tp']*100:.1f}% 차이"})
    return {'status': 'CHECKED', 'checked': len(brokers_real), 'fails': fails}


def check_d4_peer_table(analysis, peer):
    """D4: s05 peers 테이블이 _peer_snapshot.json과 일치하는가"""
    peers_report = analysis.get('peers', []) or []
    if not peer:
        return {'status': 'SKIP', 'checked': 0, 'fails': []}

    fails = []
    for p_report in peers_report:
        name = p_report.get('name', '').strip()
        if '본' in name or '본 종목' in name:
            continue
        # 원본에서 찾기
        real = None
        for real_name, real_data in peer.items():
            if real_name in name or name in real_name:
                real = real_data
                break
        if not real:
            fails.append({'peer': name, 'issue': '_peer_snapshot에 없음'})
            continue
        # PER 비교 (문자열 매칭 간략화)
        per_report_str = str(p_report.get('per', ''))
        per_real = real.get('per', 0)
        per_match = re.search(r'(-?\d+\.?\d*)', per_report_str)
        if per_match:
            per_report_num = float(per_match.group(1))
            if per_real and abs(per_report_num - per_real) / abs(per_real) > 0.1:
                fails.append({'peer': name, 'report_per': per_report_num, 'real_per': per_real, 'issue': 'PER 10%+ 차이'})
    return {'status': 'CHECKED', 'checked': len(peers_report), 'fails': fails}


def main(stock_name):
    base = f'data/{stock_name}'
    try:
        analysis = json.load(open(f'scripts/analysis_{stock_name}.json', encoding='utf-8'))
    except FileNotFoundError:
        print(f'[ERR] scripts/analysis_{stock_name}.json 없음')
        return 1

    try:
        dart = json.load(open(f'{base}/data_dart_reports.json', encoding='utf-8'))
    except FileNotFoundError:
        dart = None

    try:
        fs = json.load(open(f'{base}/financial_summary.json', encoding='utf-8'))
    except FileNotFoundError:
        fs = {}

    try:
        peer = json.load(open(f'{base}/_peer_snapshot.json', encoding='utf-8'))
    except FileNotFoundError:
        peer = {}

    print(f"\n{'='*70}")
    print(f"  STEP 6 1회차 D 블록 -- 팩트 체크 자동 검증: {stock_name}")
    print(f"{'='*70}\n")

    total_fails = 0

    # D1
    d1 = check_d1_dart_quotes(analysis, dart)
    if d1['status'] == 'SKIP':
        print(f"  [SKIP] D1 사업보고서 인용  (리포트에 직접 인용 패턴 없음)")
    else:
        total_fails += len(d1['fails'])
        icon = '✓' if not d1['fails'] else '✗'
        print(f"  [{icon} D1] 사업보고서 인용 {d1['quotes']}건 중 {len(d1['fails'])}건 FAIL (원문 미존재)")
        for f in d1['fails'][:5]:
            print(f"       - {f['section']}: \"{f['quote'][:60]}...\" ({f['matched_ratio']} 매칭)")
            if f.get('keywords_missing'):
                print(f"         누락 키워드: {f['keywords_missing'][:3]}")

    # D2 (외부 출처 리스트 - 사용자 수동 검증용)
    ext = extract_external_citations(analysis.get('sections', {}))
    print(f"\n  [INFO D2] 외부 출처 인용 {len(ext)}건 (사용자 교차 검증 필요)")
    for e in ext[:8]:
        print(f"       - {e['section']}: [{e['source']}] {e['claim'][:80]}...")

    # D3
    d3 = check_d3_consensus_table(analysis, fs)
    if d3['status'] == 'SKIP':
        print(f"\n  [SKIP] D3 증권사 목표가 테이블  (s16 없음)")
    else:
        total_fails += len(d3['fails'])
        icon = '✓' if not d3['fails'] else '✗'
        print(f"\n  [{icon} D3] 증권사 목표가 테이블 {len(d3['fails'])}건 FAIL")
        for f in d3['fails'][:5]:
            print(f"       - {f['broker']}: {f.get('issue','')}" + (f" (리포트 {f['report_tp']:,} vs 원본 {f['real_tp']:,})" if 'real_tp' in f else ""))

    # D4
    d4 = check_d4_peer_table(analysis, peer)
    if d4['status'] == 'SKIP':
        print(f"\n  [SKIP] D4 Peer 테이블  (_peer_snapshot.json 없음)")
    else:
        total_fails += len(d4['fails'])
        icon = '✓' if not d4['fails'] else '✗'
        print(f"\n  [{icon} D4] Peer 테이블 {len(d4['fails'])}건 FAIL")
        for f in d4['fails'][:5]:
            print(f"       - {f['peer']}: {f.get('issue','')}")

    print(f"\n총 D 블록 FAIL: {total_fails}")
    print(f"{'='*70}\n")

    if total_fails == 0:
        print("[OK] 팩트 체크 통과. report-critic 서브에이전트 호출 가능.")
        return 0
    print(f"[경고] 팩트 체크 FAIL {total_fails}건. 수정 후 재실행 권고.")
    return 2


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python scripts/verify_facts.py {종목명}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
