"""
STEP 6 1회차 B 블록 -- 수치 정합성 자동 검증 스크립트 (미국 종목 전용, v4.15 신설)

사용법:
    python scripts/verify_numbers_us.py {TICKER}

출력: B1~B15 항목 PASS/FAIL/SKIP + 구체적 원인.
NFLX/PANW v1 사고 (52주 고점 날조, EPS 산술 불일치, Stock split 단위 혼재) 재발 방지.

검증 항목:
- B1  시가총액 정합성 (analysis vs yfinance)
- B2  현재가 정합성 (analysis vs KIS US / yfinance)
- B3  PER/PBR 정합성
- B4  52주 고/저 정합성
- B6  Net Debt 부호/규모 일관성
- B7  EBITDA 5년 테이블 정합성
- B8  EPS 5년 테이블 정합성 (split-adj 처리)
- B10 R/R 내부 일관성 (s01 vs opinion vs s12)
- B12 Stock Split 자동 감지 → EPS 단위 일관성 검증 (NFLX 10:1 사고 방지)
- B13 GAAP vs Non-GAAP EPS 분리 여부
- B14 EPS × 발행주식 = 순이익 산술 일관성 (NFLX EPS $3.84 vs NI $12.8B 사고 방지)
- B15 DCF 공정가치 vs Base 타겟 괴리 경고 (50%+ 차이 시)
- B17 본문 핵심 수치 일관성 (v4.17 신설) -- FCF / 순부채 / 시총이 본문 여러 곳에서 다른 값으로 등장 시 FAIL
       AMD 사고: FCF $55억 vs $67억 7곳 혼재
"""
import json
import sys
import io
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_or_none(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except FileNotFoundError:
        return None


def pct_diff(a, b):
    if a is None or b is None:
        return None
    try:
        a, b = float(a), float(b)
        if b == 0:
            return None
        return abs(a - b) / abs(b) * 100
    except (TypeError, ValueError):
        return None


def main(ticker):
    analysis_path = f'scripts/analysis_{ticker}.json'
    fs_path = f'data/{ticker}/financial_summary.json'
    peer_path = f'data/{ticker}/_peer_snapshot.json'
    band_path = f'data/{ticker}/_per_band.json'
    kis_path = f'data/{ticker}/data_kis_us.json'

    d = load_or_none(analysis_path)
    fs = load_or_none(fs_path)
    peer = load_or_none(peer_path)
    band = load_or_none(band_path)
    kis = load_or_none(kis_path)

    if d is None:
        print(f'[ERR] analysis.json 없음: {analysis_path}')
        return 1
    if fs is None:
        print(f'[ERR] financial_summary.json 없음: {fs_path}')
        return 1

    ap = d.get('price', {})
    op = d.get('opinion', {})
    sections = d.get('sections', {})
    fins = fs.get('financials', {})
    yf = fs.get('yfinance', {})
    forward = fs.get('forward', {})
    kis_p = (kis.get('current_price', {}) if kis else {})

    years = sorted([y for y in fins.keys() if y.isdigit()])
    latest = years[-1] if years else None

    results = []
    fail = 0
    warn = 0

    print()
    print("=" * 70)
    print(f"  STEP 6 1회차 B 블록 -- 수치 정합성 자동 검증 (US): {ticker}")
    print("=" * 70)
    print()

    # 우선 본 종목 시세 -- yfinance 또는 peer_snapshot 활용
    yf_self = (peer.get(d['meta']['stock_name'], {}) if peer and d.get('meta') else {})

    # B1. 시가총액 정합성 (analysis vs yfinance via peer_snapshot)
    a_cap = ap.get('market_cap_num')
    yf_cap_b = yf_self.get('market_cap_b')  # B 단위
    if a_cap is not None and yf_cap_b is not None:
        # market_cap_num 단위: NFLX 39367000 = $393.67B → /100000 = B 단위
        # PANW 14786000 = $147.86B → /100000 = B 단위
        a_cap_b = float(a_cap) / 100000
        diff = pct_diff(a_cap_b, yf_cap_b)
        ok = diff is not None and diff < 5.0
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            fail += 1
        results.append(('B1 시가총액', status, f"analysis ${a_cap_b:.2f}B vs yfinance ${yf_cap_b}B (diff {diff:.1f}%)"))
    else:
        results.append(('B1 시가총액', 'SKIP', '데이터 부재'))

    # B2. 현재가 정합성
    a_curr = ap.get('current')
    kis_curr = kis_p.get('현재가') if kis_p else None
    yf_curr = yf_self.get('price')
    ref = kis_curr if kis_curr else yf_curr
    if a_curr is not None and ref is not None:
        diff = pct_diff(a_curr, ref)
        ok = diff is not None and diff < 2.0  # 시점 차이 허용
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            fail += 1
        src = "KIS" if kis_curr else "yfinance"
        results.append(('B2 현재가', status, f"analysis ${a_curr} vs {src} ${ref} (diff {diff:.1f}%)"))
    else:
        results.append(('B2 현재가', 'SKIP', '데이터 부재'))

    # B3. PER 정합성 (Trailing PE)
    a_per = ap.get('per')
    yf_per = yf_self.get('per_trailing')
    if a_per is not None and yf_per is not None:
        diff = pct_diff(a_per, yf_per)
        ok = diff is not None and diff < 5.0
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            fail += 1
        results.append(('B3 PER (TTM)', status, f"analysis {a_per}x vs yfinance {yf_per}x"))
    else:
        results.append(('B3 PER (TTM)', 'SKIP', '데이터 부재'))

    # B4. 52주 고/저 정합성 -- NFLX $152.40 날조 사고 방지
    for k_a, k_yf, label in [('high_52w', 'high_52w', '52주 고점'), ('low_52w', 'low_52w', '52주 저점')]:
        a_v = ap.get(k_a)
        ref_v = yf_self.get(k_yf)
        if a_v is not None and ref_v is not None:
            diff = pct_diff(a_v, ref_v)
            ok = diff is not None and diff < 3.0
            status = 'PASS' if ok else 'FAIL'
            if not ok:
                fail += 1
            results.append((f'B4 {label}', status, f"analysis ${a_v} vs yfinance ${ref_v} (diff {diff:.1f}%)"))
        else:
            results.append((f'B4 {label}', 'SKIP', '데이터 부재'))

    # B6. Net Debt 부호/규모 일관성
    if latest and fins.get(latest):
        nd_raw = fins[latest].get('net_debt')
        # net_debt가 없으면 long_term_debt - cash로 직접 계산
        if nd_raw is None:
            ltd = fins[latest].get('long_term_debt') or 0
            cash = fins[latest].get('cash') or 0
            sti = fins[latest].get('short_term_investments') or 0
            nd_raw = ltd - cash - sti
        nd_b = nd_raw / 1e9  # USD B
        sign = '순현금' if nd_raw < 0 else '순차입'
        expected_b = abs(nd_b)
        s08 = sections.get('s08_financial', '')
        s19 = sections.get('s19_trust_worry_watch', '')
        s02 = sections.get('s02_investment_points', '')
        combined = s02 + s08 + s19
        found = False
        for m in re.finditer(sign + r'|Net Debt', combined):
            s, e = max(0, m.start() - 30), min(len(combined), m.end() + 80)
            near = combined[s:e]
            nums = re.findall(r'\$?(\d+\.?\d*)\s*B', near)
            for num in nums:
                diff_pct = abs(float(num) - expected_b) / expected_b * 100 if expected_b else 100
                if diff_pct < 20:
                    found = True
                    break
            if found:
                break
        if found:
            results.append(('B6 Net Debt', 'PASS', f"{sign} ${expected_b:.2f}B 일관"))
        elif expected_b < 1.0:
            results.append(('B6 Net Debt', 'PASS', f"{sign} ${expected_b:.2f}B 미미 (본문 별도 언급 불필요)"))
        else:
            results.append(('B6 Net Debt', 'WARN', f"{sign} ${expected_b:.2f}B 본문 매칭 실패"))
            warn += 1
    else:
        results.append(('B6 Net Debt', 'SKIP', '최신 연도 데이터 부재'))

    # B7. EBITDA 5년 테이블 정합성
    fin_table = d.get('financials', {})
    rows = fin_table.get('rows', [])
    headers = fin_table.get('headers', [])
    ebitda_row = None
    for r in rows:
        if r and 'EBITDA' in str(r[0]):
            ebitda_row = r
            break
    if ebitda_row and len(ebitda_row) >= len(headers):
        # 각 연도별 fins[year].ebitda 와 비교
        mismatches = []
        for i, h in enumerate(headers):
            if i == 0 or 'E' in h:  # 항목명 또는 추정 연도 skip
                continue
            year = re.sub(r'[^\d]', '', h)
            if not year:
                continue
            year_full = '20' + year if len(year) == 2 else year
            if year_full not in fins:
                continue
            try:
                table_v = float(re.sub(r'[^\d.-]', '', str(ebitda_row[i])))
                fs_v = fins[year_full].get('ebitda', 0) / 1e9  # USD B
                if fs_v == 0:
                    continue
                diff = abs(table_v - fs_v) / fs_v * 100
                if diff > 5:
                    mismatches.append(f"FY{year_full}: 표 {table_v}B vs FS {fs_v:.2f}B")
            except (ValueError, TypeError):
                pass
        if mismatches:
            results.append(('B7 EBITDA', 'FAIL', '; '.join(mismatches[:3])))
            fail += 1
        else:
            results.append(('B7 EBITDA', 'PASS', '5년 테이블 정합'))
    else:
        results.append(('B7 EBITDA', 'SKIP', 'EBITDA 행 없음'))

    # B8. EPS 5년 테이블 정합성 (split-adj 자동 처리)
    # financial_summary 자체가 split-adj 미반영 케이스 처리:
    # 5년 EPS 시계열에서 8x+ 점프 발견 시 split 비율 자동 추정 후 보정
    eps_rows = [r for r in rows if r and 'EPS' in str(r[0])]

    # FS EPS 시계열에서 split 자동 감지 (10:1 또는 7:1 같은 큰 split만)
    # 작은 split (2:1, 3:1)은 일회성 이익/적자와 구분 어려우니 안전하게 무시
    fs_eps_series = [(y, fins[y].get('eps', 0)) for y in years if fins[y].get('eps')]
    split_factor = {}  # year -> divisor (e.g., {'2022': 10})
    if len(fs_eps_series) >= 3:
        for i in range(1, len(fs_eps_series)):
            y1, e1 = fs_eps_series[i-1]
            y2, e2 = fs_eps_series[i]
            if e1 == 0 or e2 == 0:
                continue
            ratio = e1 / e2 if e2 else 0
            # 6:1 이상 split만 감지 (10:1, 7:1, 3:1 단단계 추정)
            if 6 < ratio < 13 and abs(e1) > 5:  # pre-split 추정값이 의미있게 큰 경우만
                # 공식 split 비율 추정 (10:1, 7:1)
                if 8 <= ratio <= 12:
                    factor = 10
                elif 5.5 <= ratio < 8:
                    factor = 7
                else:
                    factor = round(ratio)
                for y_old in years:
                    if y_old <= y1:
                        split_factor[y_old] = factor

    if eps_rows:
        for eps_row in eps_rows[:2]:
            label = str(eps_row[0])[:35]
            # Non-GAAP 행은 FS의 GAAP EPS와 비교 부적절 -- SKIP
            if 'Non-GAAP' in label:
                results.append((f'B8 {label}', 'SKIP', 'Non-GAAP은 회사 발표값 별도 (FS GAAP과 비교 불가)'))
                continue
            mismatches = []
            for i, h in enumerate(headers):
                if i == 0 or 'E' in h:
                    continue
                year = re.sub(r'[^\d]', '', h)
                if not year:
                    continue
                year_full = '20' + year if len(year) == 2 else year
                if year_full not in fins:
                    continue
                try:
                    table_v = float(re.sub(r'[^\d.-]', '', str(eps_row[i])))
                    fs_v = fins[year_full].get('eps', 0)
                    if fs_v == 0:
                        continue
                    # split 보정 적용
                    fs_v_adj = fs_v / split_factor.get(year_full, 1)
                    diff = abs(table_v - fs_v_adj) / abs(fs_v_adj) * 100 if fs_v_adj else 0
                    if diff > 12:  # 12% 허용
                        adj_note = f" (FS split-adj ${fs_v_adj:.2f})" if year_full in split_factor else ""
                        mismatches.append(f"FY{year_full}: 표 ${table_v} vs FS ${fs_v:.2f}{adj_note}")
                except (ValueError, TypeError):
                    pass
            if mismatches:
                results.append((f'B8 {label}', 'FAIL', '; '.join(mismatches[:3])))
                fail += 1
            else:
                note = f"(split factor {split_factor})" if split_factor else ""
                results.append((f'B8 {label}', 'PASS', f'5년 테이블 정합 {note}'))
    else:
        results.append(('B8 EPS', 'SKIP', 'EPS 행 없음'))

    # B10. R/R 내부 일관성 (opinion + s01 + s12)
    rr_op = op.get('risk_reward', '')
    s01 = sections.get('s01_opinion', '')
    s12 = sections.get('s12_scenarios', '')
    bear = op.get('target_bear')
    base = op.get('target_base')
    bull = op.get('target_bull')
    curr = ap.get('current')
    if bear and base and curr:
        try:
            calc = (float(base) - float(curr)) / (float(curr) - float(bear))
            calc_str = f"1:{calc:.2f}"
            # opinion.risk_reward에 동일 비율 들어있는지
            m = re.search(r'1:?(\d+\.?\d+)', rr_op)
            if m:
                rr_v = float(m.group(1))
                diff = abs(rr_v - calc) / calc * 100 if calc else 100
                ok = diff < 10
                status = 'PASS' if ok else 'FAIL'
                if not ok:
                    fail += 1
                results.append(('B10 R/R 일관성', status,
                              f"opinion={rr_op[:30]} vs 재계산={calc_str}"))
            else:
                results.append(('B10 R/R 일관성', 'WARN', f"opinion에 R/R 비율 없음: {rr_op[:50]}"))
                warn += 1
        except (ValueError, TypeError, ZeroDivisionError):
            results.append(('B10 R/R 일관성', 'SKIP', '계산 불가'))
    else:
        results.append(('B10 R/R 일관성', 'SKIP', 'target 부재'))

    # B12. Stock Split 자동 감지 (financial_summary EPS 시계열 기준)
    # split_factor가 자동 감지되었다면 리포트가 그것을 반영했는지 확인
    if split_factor:
        # 리포트 EPS 시계열이 정합한지 위 B8에서 이미 split 보정 후 검증함
        # 여기서는 그 사실을 리포트가 명시했는지만 확인 (s08 또는 financials.source)
        src_text = str(d.get('financials', {}).get('source', '')) + str(sections.get('s08_financial', ''))
        has_split_note = 'split' in src_text.lower() or '분할' in src_text or '가산' in src_text
        if has_split_note:
            results.append(('B12 Split 처리', 'PASS', f"split factor {split_factor} 자동 감지, 리포트 명시"))
        else:
            results.append(('B12 Split 처리', 'WARN',
                          f"split factor {split_factor} 자동 감지되었으나 리포트 명시 부재"))
            warn += 1
    else:
        # 5년 시계열에 split 흔적 없음 -- 정상
        results.append(('B12 Split 처리', 'PASS', 'split 흔적 없음 (EPS 시계열 정상)'))

    # B13. GAAP vs Non-GAAP EPS 분리 여부 (US 종목 강제)
    eps_row_count = len(eps_rows)
    has_gaap = any('GAAP' in str(r[0]) and 'Non' not in str(r[0]) for r in eps_rows)
    has_nongaap = any('Non-GAAP' in str(r[0]) for r in eps_rows)
    if eps_row_count == 0:
        results.append(('B13 GAAP/Non-GAAP', 'SKIP', 'EPS 행 없음'))
    elif eps_row_count == 1 and not has_gaap:
        results.append(('B13 GAAP/Non-GAAP', 'WARN',
                      f"단일 EPS 행 ('{eps_rows[0][0]}') -- 미국 종목은 GAAP/Non-GAAP 분리 권장"))
        warn += 1
    elif has_gaap and has_nongaap:
        results.append(('B13 GAAP/Non-GAAP', 'PASS', f"{eps_row_count}개 행 분리"))
    else:
        results.append(('B13 GAAP/Non-GAAP', 'WARN', '분리 라벨링 불명확'))
        warn += 1

    # B14. EPS × 발행주식 = 순이익 산술 일관성 (NFLX $3.84 × 4.26B = $16.36B vs NI $12.8B 사고)
    # Forward 테이블에서 FY+1 또는 FY+2 의 EPS, NI, 발행주식 값 확인
    # Forward 추정 항목과 발행주식 행 매칭
    shares_row = None
    ni_row = None
    for r in rows:
        if r and ('발행주식' in str(r[0]) or 'Shares' in str(r[0])):
            shares_row = r
        if r and ('순이익' in str(r[0]) and 'GAAP' in str(r[0])) or \
           (r and '순이익' in str(r[0]) and not any('GAAP' in str(r[0]) for _ in [1])):
            if not ni_row:  # 첫 번째 (GAAP)
                ni_row = r
    # GAAP EPS row
    gaap_eps_row = next((r for r in eps_rows if 'GAAP' in str(r[0]) and 'Non' not in str(r[0])), None)
    if gaap_eps_row and ni_row and shares_row:
        # 첫 추정 연도에서 검증
        for i, h in enumerate(headers):
            if 'E' not in h or i == 0:
                continue
            try:
                eps_v = float(re.sub(r'[^\d.-]', '', str(gaap_eps_row[i])))
                ni_v = float(re.sub(r'[^\d.-]', '', str(ni_row[i])))  # B 단위
                shares_v = float(re.sub(r'[^\d.-]', '', str(shares_row[i])))  # M 단위
                # eps × shares (M) = NI (M USD), divide 1000 -> B USD
                calc_ni = eps_v * shares_v / 1000  # B USD
                diff = abs(calc_ni - ni_v) / ni_v * 100 if ni_v else 100
                if diff > 15:
                    results.append(('B14 EPS×주식=NI', 'FAIL',
                                  f"FY{h}: EPS ${eps_v} × {shares_v}M = ${calc_ni:.2f}B vs NI ${ni_v}B (diff {diff:.0f}%)"))
                    fail += 1
                    break
            except (ValueError, TypeError):
                pass
        else:
            results.append(('B14 EPS×주식=NI', 'PASS', 'Forward 산술 정합'))
    else:
        results.append(('B14 EPS×주식=NI', 'SKIP', 'GAAP EPS / 순이익 / 발행주식 행 불완전'))

    # B15. DCF 공정가치 vs Base 타겟 괴리 경고
    s09 = sections.get('s09_valuation', '')
    # DCF 주당 값 추출
    dcf_match = re.search(r'주당\s*(?:약\s*)?\$(\d+(?:\.\d+)?)', s09)
    if dcf_match and base:
        dcf_v = float(dcf_match.group(1))
        gap = (float(base) - dcf_v) / dcf_v * 100 if dcf_v else 0
        if gap > 50:
            results.append(('B15 DCF vs Base', 'WARN',
                          f"DCF ${dcf_v} vs Base ${base} (괴리 +{gap:.0f}%) -- 50%+ 프리미엄, 가정 명시 필요"))
            warn += 1
        else:
            results.append(('B15 DCF vs Base', 'PASS', f"DCF ${dcf_v} vs Base ${base} (괴리 +{gap:.0f}%)"))
    else:
        results.append(('B15 DCF vs Base', 'SKIP', 'DCF 주당 값 추출 실패'))

    # ====================================================================
    # B17 (v4.17 신설). 본문 핵심 수치 일관성 -- AMD 사고 (FCF $55억 vs $67억 7곳 혼재) 재발 방지
    # ====================================================================
    # WARN 정책: 본문에 같은 라벨로 다른 값이 여러 시점/시나리오로 등장하면
    # 시계열(FY25 vs FY28E)일 수도 있고 진짜 사고일 수도 있어 사용자가 수동 확인.
    # FAIL 자동 차단은 false positive 위험 (정상적인 forecast 표기를 사고로 오인).
    all_text = '\n\n'.join(str(v) for v in sections.values() if isinstance(v, str))

    def collect_dollar_amounts(text, label_keywords, value_range=(0.1, 5000)):
        """본문에서 라벨 직후 35자 이내 첫 금액만 수집 (정밀도 우선)
        - 라벨 직전(앞쪽)은 무시 -- 다른 지표에 속한 값이 끌려옴 방지
        - 라벨 매칭 후 첫 $X.XB / X십억 달러 / X억 달러 1개만 채택
        """
        hits = []
        # 패턴: $XXX십억 / $X.XB / X십억 달러 / X억 달러 (괄호 안 단위 포함)
        # B = 십억(billion). 한글 "억" = 100M = 0.1B.
        amount_pat = re.compile(
            r'\$\s?(\d+(?:\.\d+)?)\s*(B|십억|조)|'         # $X.XB / $X십억 / $X조
            r'(\d+(?:\.\d+)?)\s*십억\s*달러|'                # X십억 달러
            r'(\d+(?:\.\d+)?)\s*억\s*달러'                  # X억 달러
        )
        for kw in label_keywords:
            for m in re.finditer(kw, text):
                # 라벨 직후 35자 이내만 검색
                window = text[m.end(): m.end() + 35]
                v_m = amount_pat.search(window)
                if not v_m:
                    continue
                raw = v_m.group(0)
                # 그룹 추출 (어느 패턴이 매칭됐는지)
                if v_m.group(1):  # $X.XB or $X십억 or $X조
                    v = float(v_m.group(1))
                    unit = v_m.group(2)
                    if unit == '조':
                        v_b = v * 1000  # 1조 = 1000B
                    else:  # B 또는 십억
                        v_b = v
                elif v_m.group(3):  # X십억 달러
                    v_b = float(v_m.group(3))
                elif v_m.group(4):  # X억 달러 = X * 0.1B
                    v_b = float(v_m.group(4)) / 10
                else:
                    continue
                if value_range[0] < v_b < value_range[1]:
                    hits.append((v_b, raw, m.group(0)))
        return hits

    # FCF 검증 (시계열 가능성 있어 WARN만)
    fcf_hits = collect_dollar_amounts(all_text, [r'FCF', r'자유\s*현금흐름', r'잉여\s*현금'], value_range=(0.5, 200))
    if len(fcf_hits) >= 2:
        values = [v for v, _, _ in fcf_hits]
        unique = sorted(set(round(v, 1) for v in values))
        if len(unique) >= 3:  # 3개 이상 다른 값 = 시계열 + 사고 가능성 모두 존재
            results.append(('B17 FCF 본문 변종', 'WARN',
                          f"본문 FCF 값 {len(unique)}종 등장: {unique[:6]} (B USD) -- FY25/FY28E 등 시점 라벨 일관성 수동 확인"))
            warn += 1
        else:
            results.append(('B17 FCF 본문 변종', 'PASS', f"FCF 본문 {len(values)}곳, 고유값 {len(unique)}개"))
    else:
        results.append(('B17 FCF 본문 변종', 'SKIP', f"본문 FCF 라벨 매칭 {len(fcf_hits)}건"))

    # 순부채/순현금 검증
    nd_hits = collect_dollar_amounts(all_text, [r'순\s*부채', r'순\s*현금', r'Net\s*Debt', r'Net\s*Cash'], value_range=(0.5, 500))
    if len(nd_hits) >= 2:
        values = [v for v, _, _ in nd_hits]
        unique = sorted(set(round(v, 1) for v in values))
        if len(unique) >= 3:
            results.append(('B17 순부채 본문 변종', 'WARN',
                          f"본문 순부채/순현금 값 {len(unique)}종: {unique[:6]} (B USD) -- 시점/부호 수동 확인"))
            warn += 1
        else:
            results.append(('B17 순부채 본문 변종', 'PASS', f"순부채 본문 {len(values)}곳, 고유값 {len(unique)}개"))
    else:
        results.append(('B17 순부채 본문 변종', 'SKIP', f"본문 순부채 라벨 매칭 {len(nd_hits)}건"))

    # 시총 검증 (단일 시점 -- 변종 발견 시 진짜 사고 가능성 높음)
    cap_hits = collect_dollar_amounts(all_text, [r'시가\s*총액', r'시총\b'], value_range=(10, 5000))
    if len(cap_hits) >= 2:
        values = [v for v, _, _ in cap_hits]
        unique = sorted(set(round(v, 0) for v in values))
        # 시총은 시나리오별(Bear/Base/Bull) 다른 값 가능 -- 3종+면 WARN
        if len(unique) >= 3:
            results.append(('B17 시총 본문 변종', 'WARN',
                          f"본문 시총 값 {len(unique)}종: {unique[:6]} (B USD) -- 본 종목 시총 vs Peer 그룹 vs 시나리오 라벨 수동 확인"))
            warn += 1
        else:
            results.append(('B17 시총 본문 변종', 'PASS', f"시총 본문 {len(values)}곳, 고유값 {len(unique)}개"))
    else:
        results.append(('B17 시총 본문 변종', 'SKIP', f"본문 시총 라벨 매칭 {len(cap_hits)}건"))

    # ========== B11 (v5.5 신설): 컨센서스 정합성 -- KR Wisereport B11 의 미국판 ==========
    # 본문/analysis 의 Forward EPS/PER 이 yfinance 실측 컨센과 어긋나는 것을 차단.
    # 삼성전자 v4.8 사고(구 리포트 캐시를 최신 컨센으로 오인)의 미국판 재발 방지.
    cons_path = f'data/{ticker}/_us_consensus.json'
    if not os.path.exists(cons_path):
        results.append(('B11 컨센 정합', 'SKIP',
                        f'{cons_path} 없음 (us_consensus.py 미실행) -- 컨센 추이 인용했다면 수동 확인'))
    else:
        cons = json.load(open(cons_path, encoding='utf-8'))
        b11_errs = []
        est = cons.get('eps_estimate', {})
        dv = cons.get('derived', {})

        # (1) forward_eps 정합
        a_fwd_eps = ap.get('forward_eps')
        c_fwd_eps = (est.get('+1y') or {}).get('avg') or dv.get('eps_+1y_current')
        if a_fwd_eps and c_fwd_eps:
            diff = abs(float(a_fwd_eps) - float(c_fwd_eps)) / float(c_fwd_eps) * 100
            if diff > 10:
                b11_errs.append(
                    f"forward_eps {a_fwd_eps} vs 컨센 +1y {c_fwd_eps:.2f} (차이 {diff:.1f}%)")

        # (2) forward_per 정합 (현재가 / 컨센 EPS 로 역산)
        a_fwd_per = ap.get('forward_per')
        a_price = ap.get('current')
        if a_fwd_per and a_price and c_fwd_eps:
            implied = float(a_price) / float(c_fwd_eps)
            diff = abs(float(a_fwd_per) - implied) / implied * 100
            if diff > 12:
                b11_errs.append(
                    f"forward_per {a_fwd_per} vs 현재가/컨센EPS 역산 {implied:.1f} (차이 {diff:.1f}%)")

        # (3) 리비전 방향 vs 본문 서술 일관성
        direction = dv.get('consensus_direction')
        if direction in ('UP', 'DOWN'):
            up_words = ['상향', '상향조정', '컨센 상향', '추정치 상향', '눈높이 상향']
            down_words = ['하향', '하향조정', '컨센 하향', '추정치 하향', '눈높이 하향']
            said_up = any(w in all_text for w in up_words)
            said_down = any(w in all_text for w in down_words)
            mom = dv.get('revision_+1y_90d_pct')
            mom_s = f"{mom:+.1f}%" if mom is not None else "N/A"
            if direction == 'UP' and said_down and not said_up:
                b11_errs.append(
                    f"컨센 90일 {mom_s} 상향인데 본문은 '하향'으로 서술")
            elif direction == 'DOWN' and said_up and not said_down:
                b11_errs.append(
                    f"컨센 90일 {mom_s} 하향인데 본문은 '상향'으로 서술")

        # (4) 목표가 sanity: Base 타겟이 컨센 최고가를 넘으면 근거 요구
        pt = cons.get('price_targets', {})
        a_base = (d.get('opinion') or {}).get('target_base')
        if a_base and pt.get('high'):
            try:
                if float(a_base) > float(pt['high']) * 1.05:
                    b11_errs.append(
                        f"target_base ${a_base} > 컨센 최고 ${pt['high']:.0f} -- "
                        f"컨센 상단 초과 근거를 s07 밸류에이션에 명시 필요")
            except (TypeError, ValueError):
                pass

        status = 'FAIL' if b11_errs else 'PASS'
        if b11_errs:
            fail += 1
        detail = '; '.join(b11_errs)[:220] if b11_errs else (
            f"컨센 +1y EPS {c_fwd_eps:.2f} / 방향 {dv.get('consensus_direction')} / "
            f"순리비전30d {dv.get('net_revisions_+1y_30d')}" if c_fwd_eps else '컨센 정합 OK')
        results.append(('B11 컨센 정합', status, detail))

    # ========== B13 (v5.5 신설): 분기 누락 (KR 과 동일 모듈 공용) ==========
    # US 는 10-Q 가 YTD 누적이라 역산 과정에서 분기가 통째로 빠지기 쉽다.
    from quarter_labels import check as _q_check
    b13_errs, b13_detail = _q_check(d.get('quarterly', {}))
    status = 'PASS' if not b13_errs else 'FAIL'
    if b13_errs:
        fail += 1
    results.append(('B13 분기 누락', status,
                    '; '.join(b13_errs)[:220] if b13_errs else b13_detail))

    # ========== B19 (v5.5 신설): 밴드 유효성 게이트 ==========
    # _per_band.json 의 per_band_valid=False 인데 본문이 "5년 평균 대비" 를 단정하면 차단.
    band_path = f'data/{ticker}/_per_band.json'
    if os.path.exists(band_path):
        band = json.load(open(band_path, encoding='utf-8'))
        b19_errs = []
        band_claims = ['5년 평균', '역사적 평균', '5Y 평균', '밴드 상단', '밴드 하단', 'z-score', 'σ']
        claimed = [w for w in band_claims if w in all_text]
        if claimed and band.get('per_band_valid') is False:
            b19_errs.append(
                f"밴드 무효(변동계수 초과)인데 본문이 밴드 표현 사용: {claimed[:3]} -- "
                f"연도별 PER 값을 직접 제시하는 서술로 교체 필요")
        if band.get('per_band_valid') is None:
            results.append(('B19 밴드 유효성', 'SKIP', '구버전 _per_band.json (fdr_band_us.py 재실행 권장)'))
        else:
            status = 'FAIL' if b19_errs else 'PASS'
            if b19_errs:
                fail += 1
            results.append(('B19 밴드 유효성', status,
                            '; '.join(b19_errs)[:200] if b19_errs
                            else f"per_valid={band.get('per_band_valid')} / 밴드 표현 {len(claimed)}건"))
    else:
        results.append(('B19 밴드 유효성', 'SKIP', '_per_band.json 없음 (fdr_band_us.py 미실행)'))

    # 출력
    for name, status, detail in results:
        sym = {'PASS': '[PASS]', 'FAIL': '[FAIL]', 'WARN': '[WARN]', 'SKIP': '[SKIP]', 'AMBIGUOUS': '[AMBI]'}[status]
        print(f"  {sym} {name:25} {detail}")
    print()
    print(f"총 FAIL: {fail} / WARN: {warn} / 전체 체크: {len(results)}")
    print("=" * 70)

    if fail > 0:
        print(f"\n[ERROR] FAIL {fail}건 발견 -- 수정 후 PDF 재생성 권고.")
        return 2
    elif warn > 0:
        print(f"\n[NOTE] WARN {warn}건 -- 가능하면 보완 권고.")
        return 0
    else:
        print(f"\n[OK] 모든 검증 통과.")
        return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python scripts/verify_numbers_us.py {TICKER}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
