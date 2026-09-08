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
import os
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



def _match_peer(peer, name):
    """스냅샷에서 이 이름에 맞는 항목을 찾는다.

    부분문자열 관계인 두 종목(피에스케이 / 피에스케이홀딩스)이 같은 표에 있으면
    `in` 매칭은 사전 순서에 따라 엉뚱한 쪽에 붙는다. 실측으로 한 번 났다.
    그래서 ① 정확 일치 ② 공백·괄호 제거 후 정확 일치 ③ 부분 일치 중
    **이름 길이 차이가 가장 작은 것** 순으로 본다.
    """
    if not name:
        return None
    if name in peer:
        return peer[name]

    def norm(x):
        return ''.join(x.split()).replace('(', '').replace(')', '')

    n = norm(name)
    for k, v in peer.items():
        if norm(k) == n:
            return v
    # 부분 일치는 ① 질의가 후보 안에 들어가는 쪽(약칭 -> 정식명)을 먼저 보고
    # ② 그다음 이름 길이가 가장 가까운 쪽을 고른다.
    # ①이 없으면 '한화에어로'가 '한화에어로스페이스'가 아니라 '한화'에 붙는다(실측).
    cands = []
    for k in peer:
        nk = norm(k)
        if n in nk:
            cands.append((0, abs(len(nk) - len(n)), k))
        elif nk in n:
            cands.append((1, abs(len(nk) - len(n)), k))
    if not cands:
        return None
    return peer[min(cands)[2]]


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
        # 원본에서 찾기 -- 정확 일치가 부분 일치를 이긴다
        real = _match_peer(peer, name)
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

    # ========== D5 (v5.1 신설): 정관 시점 정확성 (사업보고서 [0] 정관 변경 이력 grep 매칭) ==========
    import re as _re5
    d5_fails = []
    try:
        text_concat = ' '.join(v for v in analysis.get('sections', {}).values() if isinstance(v, str))
        # 본문에서 "정관 ... YYYY.MM" 또는 "YYYY년 정관" 패턴 추출
        date_claims = _re5.findall(
            r'(20\d{2})[\.\s년]*(\d{1,2})?[\.\s월]*\d{0,2}\s*(?:정관|이사회 운영의 투명성|사업목적 변경|사채발행 액면총액)',
            text_concat
        )
        # 사업보고서 [0] 원문 (덤프 파일) 검색
        biz_path = f'data/{stock_name}/_tmp_r0_biz.txt'
        if os.path.exists(biz_path) and date_claims:
            biz_text = open(biz_path, encoding='utf-8').read()
            # "이사회 운영의 투명성 제고" 키워드의 정관 변경일 추출
            transparency_match = _re5.search(
                r'(20\d{2})[\.\s년]*\d{1,2}[\.\s월]*\d{0,2}[\s\S]{0,500}?이사회 운영의 투명성',
                biz_text
            )
            if transparency_match:
                actual_year = transparency_match.group(1)
                # 본문이 다른 연도와 "이사회 투명성"을 연결시키면 FAIL
                wrong_year_pattern = _re5.search(
                    r'(20\d{2})[\.\s년]*\d{0,2}[\.\s월]*\d{0,2}[\s\S]{0,200}?이사회 운영의 투명성',
                    text_concat
                )
                if wrong_year_pattern and wrong_year_pattern.group(1) != actual_year:
                    # 단 "정정" 또는 "사실은"같은 정정 명시가 같은 문장 안에 있으면 OK
                    surrounding = text_concat[max(0, wrong_year_pattern.start()-200):wrong_year_pattern.end()+200]
                    if not any(kw in surrounding for kw in ['정정', '사실은', '오기', actual_year + '년']):
                        d5_fails.append({
                            'claim': f'본문 \"{wrong_year_pattern.group(1)}년 이사회 운영의 투명성\"',
                            'actual': f'사업보고서 [0] 정관 변경 이력 \"{actual_year}년\"',
                            'issue': '정관 변경 시점 오기 가능성'
                        })
    except Exception:
        pass

    total_fails += len(d5_fails)
    icon = '✓' if not d5_fails else '✗'
    print(f"\n  [{icon} D5] 정관 시점 {len(d5_fails)}건 FAIL")
    for f in d5_fails[:3]:
        print(f"       - {f['claim']} (실제: {f['actual']}) - {f['issue']}")

    # ========== D6 (v5.2 신설): 4대 갭 채움 여부 자동 검증 ==========
    sections = analysis.get('sections', {})
    text_all = ' '.join(v for v in sections.values() if isinstance(v, str))
    text_s02 = sections.get('s02_thesis_catalysts', '') or sections.get('s02_business_model', '')
    text_s07 = sections.get('s07_financial_analysis', '') or sections.get('s09_valuation', '')
    text_s10 = sections.get('s10_scenarios_risks', '') or sections.get('s12_scenarios', '')
    text_s11 = sections.get('s11_earnings_consensus', '') or sections.get('s16_consensus', '')

    d6_fails = []

    # 갭1: Bear 산업 사이클 거시 데이터 의무 (v5.3: 섹터별 dynamic 키워드)
    # v5.4 패치: Bear 시나리오 박스만이 아니라 s10 전체 + s07/s11에서 산업 사이클 검색
    # (이전 패턴은 \"#### Bear (확률 X%)\" 사이만 검색하여 매크로 리스크 섹션 LME/사이클 인용 false positive 발생)
    bear_block = text_s10  # s10 전체로 확대

    # 섹터 자동 감지 + 해당 섹터 macro_sources 키워드 추가
    sector_macro_kws = []
    sector_detected = '미감지'
    sector_err = ''
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from industry_kpi import detect_industry, get_sector_matrix
        meta = analysis.get('meta', {}) or {}
        industry_field = meta.get('industry', '') or ''
        country = (meta.get('country', '') or 'KR').upper()
        if country not in ('KR', 'US'):
            country = 'KR'
        sector_detected = detect_industry(stock_name, industry_field)
        m_sector = get_sector_matrix(sector_detected, country=country)
        if m_sector:
            for src in m_sector.get('macro_sources', []):
                token = src.split()[0]
                if len(token) >= 3:
                    sector_macro_kws.append(token)
            ctc = m_sector.get('cycle_trough_compression', '')
            for kw in ['DRAM', '리튬', '임상', 'IFPI', '광고', 'NIM', '판매', '신조선가',
                       'PLF', '분양', 'ARPU', 'Cap Rate', '스프레드', '동일점포', 'Combined Ratio']:
                if kw in ctc:
                    sector_macro_kws.append(kw)
    except Exception as _e:
        sector_err = f'{type(_e).__name__}: {_e}'
    if sector_err:
        print(f"  [WARN D6] 섹터 import 실패: {sector_err} -- 일반 키워드만 사용")

    base_cycle_kws = ['역성장', '사이클', '시계열', 'YoY', '산업 매출', '산업 사이클',
                     '글로벌 시장', '시장 -', '시장 전체', '저점', '정점', '압축률']
    cycle_kws = base_cycle_kws + sector_macro_kws

    if bear_block and not any(kw in bear_block for kw in cycle_kws):
        d6_fails.append({
            'gap': 'gap1',
            'issue': f'Bear 산업 사이클 거시 데이터 부재 (감지 섹터: {sector_detected}, 기대 키워드 예: {", ".join(sector_macro_kws[:5]) if sector_macro_kws else "사이클/시계열/역성장"}) -- 단순 이벤트 나열, 일류 격차 -8점'
        })

    # 갭2: 컨센 ±20% Edge 또는 보수 사유
    rating = (analysis.get('opinion', {}) or {}).get('rating', '').upper()
    if 'BUY' in rating or 'STRONG' in rating:
        try:
            base = float((analysis.get('opinion', {}) or {}).get('target_base', 0) or 0)
            bull = float((analysis.get('opinion', {}) or {}).get('target_bull', 0) or 0)
            consensus_avg = None
            wr_path = f'data/{stock_name}/_wisereport.json'
            if os.path.exists(wr_path):
                wr = json.load(open(wr_path, encoding='utf-8'))
                consensus_avg = (wr.get('consensus', {}) or {}).get('avg_target_price')
            if consensus_avg and base:
                base_ratio = base / consensus_avg
                bull_ratio = bull / consensus_avg if bull else 0
                # BUY인데 Base 컨센 -5% 이하 + Bull 컨센 +20% 미만 + 보수 사유 부재
                conservative_box = any(kw in (text_s07 + text_s11) for kw in
                                       ['컨센 대비 보수', '컨센 보수 사유', '컨센 대비 -', 'vs 컨센', '보수 사유'])
                if base_ratio < 0.95 and bull_ratio < 1.20 and not conservative_box:
                    d6_fails.append({
                        'gap': 'gap2',
                        'issue': f'BUY rating + Base {base_ratio*100-100:+.1f}% / Bull {bull_ratio*100-100:+.1f}% 모두 컨센 추종(±5~20% 미달)인데 "컨센 대비 보수 사유" 박스 부재 -- 안전 헤지 리포트 한계, 일류 격차 -10점'
                    })
        except Exception:
            pass

    # 갭3: Self-Attack 의무 섹션
    self_attack_kws = ['Self-Attack', 'Self Attack', '자기 반박', 'thesis가 틀릴', '논문이 틀릴',
                       '본 thesis 반박', 'Thesis 반박', '본 리서치 입장']
    has_self_attack = any(kw in (text_s02 + text_s10) for kw in self_attack_kws)
    if not has_self_attack:
        d6_fails.append({
            'gap': 'gap3',
            'issue': 'Self-Attack(본 thesis가 틀릴 강한 이유 3개 + 본 리서치 입장) 박스 부재 -- 일류 88점 도달 불가, 격차 -8점'
        })

    # 갭4: 모멘텀 자기 부정 + "왜 지금" 메커니즘
    why_now_kws = ['왜 지금', '갱신 차단', 'IR 자료 부족', 'broker 모델 갱신', '컨센 무변동의 진짜 이유']
    already_priced_kws = ['이미 반영', '이미 가격', 'Sell the news', '차익실현', '차익 실현',
                          '발표를 부정', '시장이 부정']
    has_why_now = any(kw in text_s02 for kw in why_now_kws)
    has_already_priced = any(kw in (text_s02 + text_s10) for kw in already_priced_kws)
    if not (has_why_now and has_already_priced):
        missing = []
        if not has_why_now:
            missing.append('"왜 지금" 메커니즘')
        if not has_already_priced:
            missing.append('"이미 가격 반영 가능성" 부정 시나리오')
        d6_fails.append({
            'gap': 'gap4',
            'issue': f'모멘텀 자기 부정 박스 부재: {", ".join(missing)} -- 단순 시간차 가설은 70점, 격차 -8점'
        })

    total_fails += len(d6_fails)
    icon = '✓' if not d6_fails else '✗'
    print(f"\n  [{icon} D6] v5.2 4대 갭 채움 {len(d6_fails)}/4건 FAIL")
    for f in d6_fails:
        print(f"       - [{f['gap']}] {f['issue'][:140]}")

    print(f"\n총 D 블록 FAIL (B19~B22+D5+D6 포함 v5.2): {total_fails}")
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
