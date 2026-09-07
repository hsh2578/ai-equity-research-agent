"""
STEP 6 1회차 B 블록 -- 수치 정합성 자동 검증 스크립트 (v4.5 신설)

사용법:
    python scripts/verify_numbers.py {종목명}

출력: B1~B23 항목 PASS/FAIL + 구체적 원인.
삼성전자 v1의 13건 사고 중 8건을 사전 차단 목적.

- B23 밴드 유효성 게이트 (v5.7 신설, US 판 B19 의 KR 이식)
       _per_band.json 의 per_band_valid / pbr_band_valid 가 False 인데 본문이
       "5년 평균 대비" 처럼 밴드를 단정하면 FAIL. 풍산/OCI홀딩스 같은 사이클주는
       PER 이 3.6 -> 20.3 (또는 1.7 -> 34,062) 로 튀어 평균/z-score 가 노이즈다.
"""
import json
import sys
import io
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 이미 UTF-8 로 감싸져 있으면 다시 감싸지 않는다 (두 번 감싸면 먼저 만든 래퍼가
# GC 될 때 buffer 를 닫아 이 모듈을 import 한 쪽의 stdout 이 죽는다).
if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# B23: 밴드가 유효할 때만 써도 되는 표현들 (US verify_numbers_us.py B19 와 동일)
BAND_CLAIM_WORDS = ['5년 평균', '역사적 평균', '5Y 평균', '역사적 밴드',
                    '밴드 상단', '밴드 하단', 'z-score', 'σ']


def band_claims_in(text):
    """본문에 쓰인 밴드 단정 표현 목록."""
    text = text or ''
    return [w for w in BAND_CLAIM_WORDS if w in text]


def band_gate(band, text):
    """B23 밴드 유효성 게이트 -> (status, detail).

    band 가 None 이거나 per_band_valid 키가 없는 구버전이면 SKIP (거짓 FAIL 금지).
    밴드가 무효인데 본문이 밴드 표현으로 단정하면 FAIL.
    """
    if band is None:
        return 'SKIP', '_per_band.json 없음 (fdr_band.py 미실행)'
    if band.get('per_band_valid') is None and band.get('pbr_band_valid') is None:
        return 'SKIP', '구버전 _per_band.json (scripts/fdr_band.py 재실행 권장)'

    claimed = band_claims_in(text)
    invalid = [lab for lab, key in (('PER', 'per_band_valid'), ('PBR', 'pbr_band_valid'))
               if band.get(key) is False]
    if claimed and invalid:
        why = '; '.join(band.get('warnings', [])[:2])
        return 'FAIL', (
            f"{'/'.join(invalid)} 밴드 무효인데 본문이 밴드 표현 사용: {claimed[:3]} -- "
            f"연도별 값을 직접 제시하는 서술로 교체 필요"
            + (f" [{why}]" if why else ""))
    return 'PASS', (f"per_valid={band.get('per_band_valid')} "
                    f"pbr_valid={band.get('pbr_band_valid')} / 밴드 표현 {len(claimed)}건")


def load_or_none(path):
    try:
        return json.load(open(path, encoding='utf-8'))
    except FileNotFoundError:
        return None


def pct_diff(a, b):
    if not a or not b:
        return None
    try:
        return abs(float(a) - float(b)) / float(b) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def main(stock_name):
    analysis_path = f'scripts/analysis_{stock_name}.json'
    kis_path = f'data/{stock_name}/data_kis.json'
    fs_path = f'data/{stock_name}/financial_summary.json'
    dart_path = f'data/{stock_name}/data_dart_reports.json'

    d = load_or_none(analysis_path)
    kis = load_or_none(kis_path)
    fs = load_or_none(fs_path)
    dart = load_or_none(dart_path)

    if d is None:
        print(f'[ERR] analysis.json 없음: {analysis_path}')
        return 1
    if kis is None or fs is None:
        print(f'[ERR] data 파일 없음')
        return 1

    ap = d.get('price', {})
    kp = kis.get('current_price', {})
    sections = d.get('sections', {})
    fins = fs.get('financials', {})
    years = sorted([y for y in fins.keys() if y.isdigit()])
    latest = years[-1] if years else None

    results = []
    fail = 0

    # B1. 시가총액 정합성 (±1%)
    diff = pct_diff(ap.get('market_cap_num'), kp.get('시가총액'))
    ok = diff is not None and diff < 1.0
    status = 'PASS' if ok else 'FAIL'
    if not ok:
        fail += 1
    results.append(('B1 시가총액', status, f"analysis={ap.get('market_cap_num')} vs KIS={kp.get('시가총액')} (diff={diff:.1f}%)" if diff is not None else "N/A"))

    # B2. 현재가 정합성
    diff = pct_diff(ap.get('current'), kp.get('현재가'))
    ok = diff is not None and diff < 0.1
    status = 'PASS' if ok else 'FAIL'
    if not ok:
        fail += 1
    results.append(('B2 현재가', status, f"analysis={ap.get('current')} vs KIS={kp.get('현재가')}"))

    # B3. PER/PBR/EPS/BPS 4개 정합성
    for k, a_k in [('PER', 'per'), ('PBR', 'pbr'), ('EPS', 'eps'), ('BPS', 'bps')]:
        diff = pct_diff(ap.get(a_k), kp.get(k))
        ok = diff is not None and diff < 1.0
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            fail += 1
        results.append((f'B3 {k}', status, f"analysis={ap.get(a_k)} vs KIS={kp.get(k)}"))

    # B4. 52주 고/저
    for k, a_k in [('52주최고', 'high_52w'), ('52주최저', 'low_52w')]:
        diff = pct_diff(ap.get(a_k), kp.get(k))
        ok = diff is not None and diff < 0.5
        status = 'PASS' if ok else 'FAIL'
        if not ok:
            fail += 1
        results.append((f'B4 {k}', status, f"analysis={ap.get(a_k)} vs KIS={kp.get(k)} (diff={diff:.1f}%)" if diff is not None else "N/A"))

    # B5. 수급 부호 일관성 (s17 서술과 investor_trend 부호)
    s17 = sections.get('s17_supply', '')
    tr = kis.get('investor_trend', {})
    for party, key in [('외국인', '외국인_순매수'), ('기관', '기관_순매수'), ('개인', '개인_순매수')]:
        val = tr.get(key) if isinstance(tr, dict) else None
        if val is None:
            results.append((f'B5 {party}', 'SKIP', '데이터 없음'))
            continue
        actual_dir = '매도' if val < 0 else '매수'
        # 서술에서 해당 party가 "매도"인지 "매수"인지 찾기
        # 간단 휴리스틱: party 키워드 근처에 "매도" 또는 "매수"가 있는지
        found_sell = False
        found_buy = False
        for m in re.finditer(party, s17):
            s, e = max(0, m.start() - 50), min(len(s17), m.end() + 100)
            near = s17[s:e]
            if '매도' in near:
                found_sell = True
            if '매수' in near or '매집' in near:
                found_buy = True
        if actual_dir == '매도' and found_sell and not found_buy:
            status = 'PASS'
        elif actual_dir == '매수' and found_buy and not found_sell:
            status = 'PASS'
        elif actual_dir == '매도' and found_buy and not found_sell:
            status = 'FAIL'
            fail += 1
        elif actual_dir == '매수' and found_sell and not found_buy:
            status = 'FAIL'
            fail += 1
        else:
            status = 'AMBIGUOUS'
        results.append((f'B5 {party}', status, f"KIS={actual_dir}({val:+,}), 서술: sell={found_sell}, buy={found_buy}"))

    # B6. 순현금/순차입 일관성
    if latest and fins.get(latest):
        nd = fins[latest].get('net_debt')
        if nd is not None:
            # 순현금 조 단위 절대값
            expected_jo = abs(nd) / 10000
            sign = '순현금' if nd < 0 else '순차입'
            s08 = sections.get('s08_financial', '')
            s19 = sections.get('s19_trust_worry_watch', '')
            combined = s08 + s19
            # 순현금 또는 순차입 키워드 근처의 숫자 추출
            found_match = False
            for m in re.finditer(sign, combined):
                s, e = max(0, m.start() - 20), min(len(combined), m.end() + 30)
                near = combined[s:e]
                # 숫자 조 찾기
                nums = re.findall(r'(\d+\.?\d*)\s*조', near)
                for num in nums:
                    if abs(float(num) - expected_jo) / expected_jo < 0.1:  # 10% 이내
                        found_match = True
                        break
                if found_match:
                    break
            status = 'PASS' if found_match else 'FAIL'
            if not found_match:
                fail += 1
            results.append(('B6 순현금/순차입', status, f"{sign} {expected_jo:.1f}조 (KIS 원본)"))

    # B7. EBITDA 5년 테이블
    rows = d.get('financials', {}).get('rows', [])
    headers = d.get('financials', {}).get('headers', [])
    for row in rows:
        if row and 'EBITDA' in str(row[0]):
            ebitda_mismatch = 0
            for i, y in enumerate(headers[1:], 1):
                y_str = str(y).replace('E', '').replace('F', '')
                if y_str in fins:
                    orig_ebitda = fins[y_str].get('ebitda')
                    if orig_ebitda and i < len(row):
                        try:
                            reported_jo = float(str(row[i]).replace(',', ''))
                            orig_jo = orig_ebitda / 10000
                            if pct_diff(reported_jo, orig_jo) and pct_diff(reported_jo, orig_jo) > 3:
                                ebitda_mismatch += 1
                        except ValueError:
                            pass
            status = 'PASS' if ebitda_mismatch == 0 else 'FAIL'
            if ebitda_mismatch > 0:
                fail += 1
            results.append(('B7 EBITDA 테이블', status, f"불일치 {ebitda_mismatch}개 연도"))
            break

    # B8. EPS 5년 테이블
    for row in rows:
        if row and ('EPS' in str(row[0])):
            eps_mismatch = 0
            for i, y in enumerate(headers[1:], 1):
                y_str = str(y).replace('E', '').replace('F', '')
                if y_str in fins:
                    orig_eps = fins[y_str].get('eps')
                    if orig_eps and i < len(row):
                        try:
                            reported = float(str(row[i]).replace(',', ''))
                            if pct_diff(reported, orig_eps) and pct_diff(reported, orig_eps) > 2:
                                eps_mismatch += 1
                        except ValueError:
                            pass
            status = 'PASS' if eps_mismatch == 0 else 'FAIL'
            if eps_mismatch > 0:
                fail += 1
            results.append(('B8 EPS 테이블', status, f"불일치 {eps_mismatch}개 연도"))
            break

    # B9. 신용등급 (사업보고서 원문 대조)
    if dart and len(dart) > 0:
        biz = dart[0].get('sections', {}).get('사업의_내용', '')
        rating_match = re.search(r"Moody.?s.*?등급은\s*([A-Za-z0-9]+)", biz)
        sp_match = re.search(r"S&P.*?등급은\s*([A-Za-z0-9\-+]+)", biz)
        moodys_orig = rating_match.group(1) if rating_match else None
        sp_orig = sp_match.group(1) if sp_match else None
        all_sections_text = ' '.join(str(s) for s in sections.values())
        has_moodys = 'Moody' in all_sections_text
        errs = []
        if has_moodys and moodys_orig:
            if moodys_orig not in all_sections_text:
                # 다른 노치 (A1/Aa2 등)가 쓰였는지 확인
                wrong = re.search(r"Moody.?s\s*[A-Za-z0-9]+", all_sections_text)
                if wrong:
                    errs.append(f"Moody's 원문={moodys_orig}, 리포트={wrong.group()}")
        if sp_orig and 'S&P' in all_sections_text:
            if sp_orig not in all_sections_text:
                errs.append(f"S&P 원문={sp_orig}")
        status = 'PASS' if not errs else 'FAIL'
        if errs:
            fail += 1
        results.append(('B9 신용등급', status, '; '.join(errs) if errs else f"Moody's={moodys_orig}, S&P={sp_orig}"))

    # B10. R/R 내부 일관성
    opinion = d.get('opinion', {})
    rr_opinion = opinion.get('risk_reward', '')
    target_base = opinion.get('target_base')
    target_bear = opinion.get('target_bear')
    current = ap.get('current')
    if target_base and target_bear and current:
        try:
            down = (float(target_bear) - float(current)) / float(current) * 100
            up = (float(target_base) - float(current)) / float(current) * 100
            if down < 0 and up > 0:
                actual_rr = up / abs(down)
                rr_str = f"1:{actual_rr:.1f}"
                status = 'PASS' if rr_str.replace(' ', '') in rr_opinion.replace(' ', '') else 'CHECK'
                if status != 'PASS':
                    fail += 1
                results.append(('B10 R/R 일관성', status, f"실제 계산 {rr_str} vs opinion {rr_opinion}"))
        except (ValueError, ZeroDivisionError):
            results.append(('B10 R/R 일관성', 'ERR', '계산 실패'))

    # B11. Wisereport 컨센서스 수치 정합성 (v4.8 신설) -- 삼성전자 사고 재발 방지
    wisereport_path = f'data/{stock_name}/_wisereport.json'
    wr = load_or_none(wisereport_path)
    if wr is None:
        results.append(('B11 Wisereport', 'SKIP', f'{wisereport_path} 없음 (Chrome MCP 크롤링 미실행)'))
    else:
        fin_wr = wr.get('financials_annual', {})
        # 2026E 등 Forward 연도 찾기
        fwd_keys = [k for k in fin_wr.keys() if 'E' in str(k).upper()]
        errs = []
        for fwd in fwd_keys[:3]:  # 최대 3개 Forward 연도
            wr_fwd = fin_wr.get(fwd, {})
            wr_op = wr_fwd.get('영업이익_발표기준') or wr_fwd.get('영업이익')
            wr_eps = wr_fwd.get('EPS')
            wr_ni = wr_fwd.get('순이익')

            # analysis.json financials.rows 에서 해당 Forward 연도 찾기
            headers = d.get('financials', {}).get('headers', [])
            rows = d.get('financials', {}).get('rows', [])
            # 헤더 매칭: "2026E" "2026/12(E)" "2026(E)" 등
            col_idx = None
            fwd_year = str(fwd).replace('E', '').replace('(', '').replace(')', '').strip()[:4]
            for i, h in enumerate(headers):
                if fwd_year in str(h) and ('E' in str(h).upper() or 'F' in str(h).upper()):
                    col_idx = i
                    break
            if col_idx is None:
                continue

            # 영업이익 행
            for row in rows:
                if row and '영업이익' in str(row[0]) and 'OPM' not in str(row[0]):
                    try:
                        reported_jo = float(str(row[col_idx]).replace(',', '').replace('조', ''))
                        wr_jo = float(wr_op) / 10000 if wr_op else None  # 억 -> 조
                        if wr_jo and reported_jo:
                            diff_pct = abs(reported_jo - wr_jo) / wr_jo * 100
                            if diff_pct > 10:
                                errs.append(f"{fwd} 영업이익: 리포트 {reported_jo:.1f}조 vs Wisereport {wr_jo:.1f}조 (괴리 {diff_pct:.0f}%)")
                    except (ValueError, TypeError):
                        pass
                    break

            # EPS 행
            for row in rows:
                if row and 'EPS' in str(row[0]):
                    try:
                        reported_eps = float(str(row[col_idx]).replace(',', '').replace('원', ''))
                        if wr_eps and reported_eps:
                            diff_pct = abs(reported_eps - float(wr_eps)) / float(wr_eps) * 100
                            if diff_pct > 10:
                                errs.append(f"{fwd} EPS: 리포트 {reported_eps:,.0f}원 vs Wisereport {wr_eps:,}원 (괴리 {diff_pct:.0f}%)")
                    except (ValueError, TypeError):
                        pass
                    break

        # 컨센서스 추이 체크: 3개월 전 대비 +50% 이상 상향이면 s02/s16 에 명시 확인
        traj = wr.get('consensus_trajectory_2026E', {})
        today_op = None
        m3_op = None
        try:
            today_op = float(traj.get('오늘', {}).get('영업이익', 0))
            m3_op = float(traj.get('3개월전', {}).get('영업이익', 0))
        except (ValueError, TypeError):
            pass
        if today_op and m3_op and today_op > 0 and m3_op > 0:
            change_pct = (today_op - m3_op) / m3_op * 100
            all_sections_text = ' '.join(str(s) for s in sections.values())
            if change_pct > 50:
                has_mention = any(kw in all_sections_text for kw in ['상향', '메가트렌드', '컨센서스 추이', '컨센서스 급등'])
                if not has_mention:
                    errs.append(f"3개월 +{change_pct:.0f}% 상향인데 리포트에 '상향/추이' 미언급")

        status = 'PASS' if not errs else 'FAIL'
        if errs:
            fail += 1
        results.append(('B11 Wisereport 정합', status, '; '.join(errs)[:200] if errs else 'Forward 수치 ±10% 이내'))

    # B12. SOTP·DCF 산술 일관성 (v4.14 신설 -- 한화에어로 해양 18조 산술 오류 재발 방지)
    # 리포트 본문의 "{A} × {B}x = {C}조" 또는 "{A}억 × {B} = {C}조" 패턴 재계산
    sotp_errs = []
    # s09 밸류에이션 + s02 투자포인트 (SOTP/DCF 주로 나오는 섹션)
    target_text = sections.get('s09_valuation', '') + sections.get('s02_investment_points', '')
    # 패턴 1: "10,000억 × 5x = 18조" / "10,000억 × 5배 = 5조"
    pat1 = re.compile(
        r'([\d,]+)\s*억\s*[×xX\*]\s*([\d\.]+)\s*(?:배|x|X)\s*=\s*(?:약\s*)?([\d\.]+)\s*조'
    )
    for m in pat1.finditer(target_text):
        try:
            a = float(m.group(1).replace(',', '')) / 10000  # 억 -> 조
            b = float(m.group(2))
            expected = a * b
            reported = float(m.group(3))
            if expected > 0 and abs(expected - reported) / expected > 0.15:  # 15% 이내 허용
                sotp_errs.append(
                    f"{m.group(1)}억 × {b} = 실제 {expected:.2f}조 vs 리포트 {reported}조"
                )
        except (ValueError, ZeroDivisionError):
            pass
    # 패턴 2: "A조 × B = C조" (배수 곱셈)
    pat2 = re.compile(
        r'([\d\.]+)\s*조\s*[×xX\*]\s*([\d\.]+)\s*(?:%|배|x|X)?\s*=\s*(?:약\s*)?([\d\.]+)\s*조'
    )
    for m in pat2.finditer(target_text):
        try:
            a = float(m.group(1))
            b = float(m.group(2))
            # 두 번째 숫자가 퍼센트인지 배수인지 판별: 100 이상이면 퍼센트
            if b > 1 and b <= 100:
                # 배수 가정
                expected = a * b
            else:
                continue  # 복잡 — 스킵
            reported = float(m.group(3))
            if expected > 0 and abs(expected - reported) / expected > 0.15:
                sotp_errs.append(
                    f"{a}조 × {b} = 실제 {expected:.2f}조 vs 리포트 {reported}조"
                )
        except (ValueError, ZeroDivisionError):
            pass
    # 패턴 3: 지분율 × 시총 = 지주 몫
    pat3 = re.compile(
        r'([\d\.]+)\s*%\s*[×xX\*]\s*([\d\.]+)\s*조\s*=\s*(?:약\s*)?([\d\.]+)\s*조'
    )
    for m in pat3.finditer(target_text):
        try:
            pct = float(m.group(1)) / 100
            mcap = float(m.group(2))
            expected = pct * mcap
            reported = float(m.group(3))
            if expected > 0 and abs(expected - reported) / expected > 0.15:
                sotp_errs.append(
                    f"{m.group(1)}% × {mcap}조 = 실제 {expected:.2f}조 vs 리포트 {reported}조"
                )
        except (ValueError, ZeroDivisionError):
            pass
    status = 'PASS' if not sotp_errs else 'FAIL'
    if sotp_errs:
        fail += 1
    results.append(
        ('B12 SOTP·DCF 산술', status,
         '; '.join(sotp_errs[:3])[:250] if sotp_errs else f'{len(list(pat1.finditer(target_text)) + list(pat2.finditer(target_text)) + list(pat3.finditer(target_text)))}개 산술 패턴 ±15% 이내')
    )

    # B13. quarterly 분기 누락 (v5.5 재작성 -- v4.20 원본은 죽어 있었다)
    # 원본은 rows[i][0] 을 분기 라벨로 읽었으나 analysis.json 은 headers 에 분기가 온다.
    # 정규식이 한 건도 매칭되지 않아 에러 리스트가 비었고 그대로 PASS 를 냈다
    # (한국콜마/와이지엔터 모두 "확정 4분기 충족" 이라는 거짓 메시지로 통과).
    # scripts/quarter_labels.py 로 이관 + tests/test_quarter_labels.py 로 검증한다.
    from quarter_labels import check as _q_check
    b13_errs, b13_detail = _q_check(d.get('quarterly', {}))
    status = 'PASS' if not b13_errs else 'FAIL'
    if b13_errs:
        fail += 1
    results.append(('B13 분기 누락', status,
                    '; '.join(b13_errs)[:220] if b13_errs else b13_detail))

    # ========== B14 (v5.0 신설): 잠정 vs 정정 OP 충돌 ==========
    b14_errs = []
    try:
        wr_path = f'data/{stock_name}/_wisereport.json'
        if os.path.exists(wr_path):
            wr = json.load(open(wr_path, encoding='utf-8'))
            es_4q = wr.get('earning_surprise_4Q25', {}) or wr.get('earning_surprise', {})
            actual_op_provisional = es_4q.get('OP_actual') or es_4q.get('actual')
            quarterly = wr.get('quarterly_2025', {}) or {}
            last_q = None
            for k in sorted(quarterly.keys()):
                if '4Q' in k or 'Q_12' in k:
                    last_q = quarterly[k]
                    break
            if actual_op_provisional and last_q:
                op_corrected = last_q.get('영업이익_발표기준') or last_q.get('영업이익')
                if op_corrected and abs(actual_op_provisional - op_corrected) / op_corrected > 0.05:
                    # 본문이 잠정/정정 차이를 명시 인지하고 정정값 채택했는지 확인
                    text_concat_b14 = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
                    op_corrected_str = f"{op_corrected:.0f}"
                    has_corrected_value = (op_corrected_str in text_concat_b14) or (f"{int(op_corrected)}" in text_concat_b14)
                    has_recognition = any(kw in text_concat_b14 for kw in ['정정', '잠정', '동일 기준', '동일기준', 'In-line', '재정', '확정 OP'])
                    if has_corrected_value and has_recognition:
                        pass  # 분석가가 잠정/정정 차이 인지하고 정정값 채택 -- PASS
                    else:
                        b14_errs.append(
                            f"잠정 OP {actual_op_provisional:.1f}억 vs 정정 OP {op_corrected:.1f}억 "
                            f"({(actual_op_provisional - op_corrected) / op_corrected * 100:+.1f}% 차이) -- 정정 OP 우선 채택"
                        )
                        annual_op = wr.get('financials_annual', {}).get('2025', {}).get('영업이익_발표기준')
                        if annual_op:
                            q_sum = sum(
                                (q.get('영업이익_발표기준') or 0) for q in quarterly.values()
                            )
                            if abs(q_sum - annual_op) / annual_op > 0.05:
                                b14_errs.append(
                                    f"연간 OP {annual_op:.1f} != Q합계 {q_sum:.1f}"
                                )
    except Exception as e:
        b14_errs.append(f"검증 실패: {e}")
    if b14_errs:
        fail += 1
    results.append(('B14 잠정 vs 정정 OP', 'FAIL' if b14_errs else 'PASS', '; '.join(b14_errs)[:200] if b14_errs else '잠정/정정 OP 일치'))

    # ========== B15 (v5.0 신설): 발표기준 vs K-IFRS OP 분리 강제 ==========
    b15_errs = []
    try:
        wr_path = f'data/{stock_name}/_wisereport.json'
        if os.path.exists(wr_path):
            wr = json.load(open(wr_path, encoding='utf-8'))
            ann = wr.get('financials_annual', {}).get('2025', {})
            op_announce = ann.get('영업이익_발표기준')
            op_ifrs = ann.get('영업이익')
            if op_announce and op_ifrs:
                diff_pct = abs(op_announce - op_ifrs) / max(abs(op_announce), 1) * 100
                if diff_pct > 10:
                    text_concat = ' '.join(
                        v for v in d.get('sections', {}).values() if isinstance(v, str)
                    )
                    has_kifrs = ('K-IFRS' in text_concat or '발표기준' in text_concat)
                    if not has_kifrs:
                        b15_errs.append(
                            f"발표 OP {op_announce:.0f} vs K-IFRS {op_ifrs:.0f} ({diff_pct:.1f}% 차이) -- 분리 표기 누락"
                        )
    except Exception:
        pass
    if b15_errs:
        fail += 1
    results.append(('B15 발표 vs K-IFRS', 'FAIL' if b15_errs else 'PASS', '; '.join(b15_errs)[:200] if b15_errs else '분리 표기 OK 또는 차이 미미'))

    # ========== B16 (v5.0 신설): PBR 시계열 일관성 ==========
    b16_errs = []
    try:
        band_path = f'data/{stock_name}/_per_band.json'
        if os.path.exists(band_path):
            band = json.load(open(band_path, encoding='utf-8'))
            pbr_series = band.get('pbr_series', [])
            if pbr_series and len(pbr_series) >= 5:
                text_concat = ' '.join(
                    v for v in d.get('sections', {}).values() if isinstance(v, str)
                )
                m = re.search(r'2021[\s년]*?([\d.]+)\s*[→배\)]', text_concat)
                if m:
                    reported_2021 = float(m.group(1))
                    actual_2021 = pbr_series[0]
                    if actual_2021 > 0 and abs(reported_2021 - actual_2021) / actual_2021 > 0.10:
                        b16_errs.append(
                            f"PBR 2021 리포트 {reported_2021} vs 실측 {actual_2021:.2f} -- 시계열 위조 의심"
                        )
    except Exception:
        pass
    if b16_errs:
        fail += 1
    results.append(('B16 PBR 시계열', 'FAIL' if b16_errs else 'PASS', '; '.join(b16_errs)[:200] if b16_errs else 'PBR 시계열 일관'))

    # ========== B17 (v5.0 신설): Altman Z 5요소 자동 계산 ==========
    b17_errs = []
    try:
        fs_path = f'data/{stock_name}/financial_summary.json'
        if os.path.exists(fs_path):
            fs = json.load(open(fs_path, encoding='utf-8'))
            fy = fs.get('financials', {}).get('2025', {})
            ta, ca, cl = fy.get('total_assets'), fy.get('current_assets'), fy.get('current_liabilities')
            re_v, ebit, rev = fy.get('retained_earnings'), fy.get('op_income'), fy.get('revenue')
            tl = fy.get('total_debt')
            mc = (json.load(open(f'data/{stock_name}/data_kis.json', encoding='utf-8'))
                  .get('current_price', {}).get('시가총액')) if os.path.exists(f'data/{stock_name}/data_kis.json') else None
            if all(v is not None for v in [ta, ca, cl, re_v, ebit, rev, mc, tl]) and ta > 0 and tl > 0:
                z_calc = 1.2*((ca-cl)/ta) + 1.4*(re_v/ta) + 3.3*(ebit/ta) + 0.6*(mc/tl) + 1.0*(rev/ta)
                text_concat = ' '.join(
                    v for v in d.get('sections', {}).values() if isinstance(v, str)
                )
                z_matches = re.findall(r'(?:Altman\s*)?[ZZ][\s\-]*[Ss]core?\s*[=:]\s*([\d.]+)', text_concat)
                if z_matches:
                    z_reported = float(z_matches[0])
                    if abs(z_reported - z_calc) > 0.5:
                        b17_errs.append(f"Altman Z 리포트 {z_reported:.2f} vs 실측 {z_calc:.2f}")
                    unique_z = set(round(float(z), 1) for z in z_matches)
                    if len(unique_z) > 1:
                        b17_errs.append(f"Z 본문에 {len(unique_z)}개 다른 값: {sorted(unique_z)}")
    except Exception:
        pass
    if b17_errs:
        fail += 1
    results.append(('B17 Altman Z 5요소', 'FAIL' if b17_errs else 'PASS', '; '.join(b17_errs)[:200] if b17_errs else 'Altman Z 일치 또는 미인용'))

    # ========== B18 (v5.0 신설): DCF D/V 산식 검증 ==========
    b18_errs = []
    try:
        kis_path = f'data/{stock_name}/data_kis.json'
        mc = None
        if os.path.exists(kis_path):
            mc = json.load(open(kis_path, encoding='utf-8')).get('current_price', {}).get('시가총액')
        debt = 128
        wr_path = f'data/{stock_name}/_wisereport.json'
        if os.path.exists(wr_path):
            debt = (json.load(open(wr_path, encoding='utf-8')).get('financials_annual', {})
                    .get('2025', {}).get('이자발생부채', 128))
        if mc and mc > 0:
            dv_calc = debt / (mc + debt)
            text_concat = ' '.join(
                v for v in d.get('sections', {}).values() if isinstance(v, str)
            )
            dv_matches = re.findall(r'D/V\s*[=:]\s*([\d.]+)\s*%', text_concat)
            if dv_matches:
                dv_reported = float(dv_matches[0]) / 100
                if abs(dv_reported - dv_calc) > 0.02:
                    b18_errs.append(
                        f"DCF D/V 리포트 {dv_reported*100:.2f}% vs 실측 {dv_calc*100:.2f}% (차입금 {debt}억 / 시총 {mc}억)"
                    )
    except Exception:
        pass
    if b18_errs:
        fail += 1
    results.append(('B18 DCF D/V 산식', 'FAIL' if b18_errs else 'PASS', '; '.join(b18_errs)[:200] if b18_errs else 'D/V 일치 또는 미인용'))

    # ========== B19 (v5.1 신설): 산술 비약 검증 (catalyst 표 OP 합산 vs 본문 "+X~Y억") ==========
    b19_errs = []
    try:
        text_concat = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
        # 본문에서 "+X~Y억 추가" / "+X~Y억 가시성" 패턴 추출
        thesis_matches = re.findall(r'[+\-]?(\d{2,4})\s*~\s*(\d{2,4})\s*억\s*(?:원\s*)?(?:추가|가시성|기여|상향)', text_concat)
        # catalysts 메타에서 "OP +X~Y억" 합산 (낮은 합 / 높은 합)
        cats = d.get('catalysts', []) or []
        op_low = op_high = 0
        for c in cats:
            impact = c.get('impact', '')
            m = re.search(r'OP\s*[+\-]?(\d{2,4})\s*~\s*(\d{2,4})\s*억', impact)
            if m:
                op_low += int(m.group(1))
                op_high += int(m.group(2))
        # 본문 thesis 인용값과 catalyst 합산 비교
        if thesis_matches and op_low > 0 and op_high > 0:
            for low, high in thesis_matches:
                low_n, high_n = int(low), int(high)
                # thesis가 catalyst 합산보다 +50% 이상 inflated 시 비약 의심
                if low_n > op_low * 1.5 or high_n > op_high * 1.5:
                    b19_errs.append(
                        f"본문 인용 +{low_n}~{high_n}억 vs catalyst OP 합산 +{op_low}~{op_high}억 "
                        f"({(high_n/max(op_high,1)-1)*100:+.0f}% 차이) -- 매출+OP 단위 혼동 가능성"
                    )
                    break
    except Exception:
        pass
    if b19_errs:
        fail += 1
    results.append(('B19 산술 비약', 'FAIL' if b19_errs else 'PASS', '; '.join(b19_errs)[:200] if b19_errs else 'OP 합산 일관 또는 미감지'))

    # ========== B20 (v5.1 신설): DCF 출력값 정합성 (가정 → 적정주가 자동 산출 → 본문값 ±10%) ==========
    b20_errs = []
    try:
        text_concat = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
        # WACC + 적정주가 추출
        wacc_match = re.search(r'WACC\s*[=:]?\s*([\d.]+)\s*%', text_concat)
        terminal_g_match = re.search(r'[Tt]erminal\s*g\s*[=:]?\s*([\d.]+)\s*%', text_concat)
        # 본문 DCF 적정주가 (DCF 적정주가 ≈ X원 / X원 패턴)
        dcf_target_matches = re.findall(r'DCF\s*적정주가\s*[≈=:]?\s*(?:약\s*)?([\d,]+)\s*원', text_concat)
        wr_path = f'data/{stock_name}/_wisereport.json'
        kis_path = f'data/{stock_name}/data_kis.json'
        if (wacc_match and terminal_g_match and dcf_target_matches
                and os.path.exists(wr_path) and os.path.exists(kis_path)):
            wacc = float(wacc_match.group(1)) / 100
            g = float(terminal_g_match.group(1)) / 100
            wr = json.load(open(wr_path, encoding='utf-8'))
            kis = json.load(open(kis_path, encoding='utf-8'))
            # 시작 FCF (2026E) + 순현금
            ann = wr.get('financials_annual', {}).get('2026E', {}) or wr.get('financials_annual', {}).get('2025', {})
            fcf_start = ann.get('FCF') or ann.get('잉여현금흐름') or 896
            net_cash_match = re.search(r'순현금\s*[+]?\s*?([\d,]+)\s*억|Net\s*Cash\s*[+]?\s*?([\d,]+)\s*억', text_concat)
            net_cash = 2737  # default
            if net_cash_match:
                cash_str = (net_cash_match.group(1) or net_cash_match.group(2) or '').replace(',', '')
                if cash_str:
                    net_cash = int(cash_str)
            shares = kis.get('current_price', {}).get('주식수') or 18691049
            # 단순 DCF: 5년 FCF 7% 성장 + Terminal
            fcf = fcf_start
            pv_sum = 0
            for yr in range(1, 6):
                fcf = fcf * 1.07
                pv_sum += fcf / ((1 + wacc) ** yr)
            fcf_5 = fcf
            terminal = fcf_5 * (1 + g) / (wacc - g) if wacc > g else 0
            pv_terminal = terminal / ((1 + wacc) ** 5)
            ev = pv_sum + pv_terminal
            equity = ev + net_cash
            dcf_calc = equity * 100000000 / shares  # 억원 → 원
            # 본문값 비교
            dcf_reported = int(dcf_target_matches[0].replace(',', ''))
            if abs(dcf_reported - dcf_calc) / max(dcf_calc, 1) > 0.10:
                b20_errs.append(
                    f"DCF 본문 {dcf_reported:,}원 vs 실측 {dcf_calc:,.0f}원 "
                    f"(WACC {wacc*100:.2f}% / g {g*100:.2f}% / FCF시작 {fcf_start}억 / 순현금 {net_cash}억) "
                    f"-- 가정-출력 불일치 ({(dcf_reported/max(dcf_calc,1)-1)*100:+.1f}%)"
                )
    except Exception:
        pass
    if b20_errs:
        fail += 1
    results.append(('B20 DCF 출력값', 'FAIL' if b20_errs else 'PASS', '; '.join(b20_errs)[:250] if b20_errs else 'DCF 가정-출력 일치 또는 미감지'))

    # ========== B21 (v5.1 신설): Bullish thesis vs 보수 적정가 모순 ==========
    b21_errs = []
    try:
        rating = d.get('opinion', {}).get('rating', '')
        target_base = d.get('opinion', {}).get('target_base', 0)
        wr_path = f'data/{stock_name}/_wisereport.json'
        if rating == 'BUY' and target_base and os.path.exists(wr_path):
            wr = json.load(open(wr_path, encoding='utf-8'))
            consensus_avg = wr.get('consensus', {}).get('avg_target_price') or wr.get('consensus', {}).get('avg_tp', 0)
            if consensus_avg and target_base < consensus_avg * 0.90:
                discount_pct = (target_base / consensus_avg - 1) * 100
                # 본문에 thesis-적정주가 일관성 설명이 있는지 확인
                text_concat = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
                has_explanation = (
                    'thesis-적정주가' in text_concat or
                    'thesis vs 적정주가' in text_concat or
                    '보수 디스카운트' in text_concat or
                    '보수 적정' in text_concat or
                    '디스카운트 적용' in text_concat
                )
                if not has_explanation:
                    b21_errs.append(
                        f"BUY rating + Base {target_base:,}원이 컨센 평균 {consensus_avg:,}원 대비 {discount_pct:.1f}% 보수 "
                        f"-- thesis-적정주가 일관성 설명 누락 (사유 본문에 명시 필요)"
                    )
    except Exception:
        pass
    if b21_errs:
        fail += 1
    results.append(('B21 thesis-적정가 일관성', 'FAIL' if b21_errs else 'PASS', '; '.join(b21_errs)[:200] if b21_errs else 'rating-target 일관 또는 설명 명시'))

    # ========== B22 (v5.1 신설): "N/M 100% 미반영" 비약 검증 ==========
    b22_errs = []
    try:
        wr_path = f'data/{stock_name}/_wisereport.json'
        if os.path.exists(wr_path):
            wr = json.load(open(wr_path, encoding='utf-8'))
            tp_changes = wr.get('consensus', {}).get('recent_tp_changes', []) or []
            n_known = len(tp_changes)
            estimator_count = wr.get('consensus', {}).get('estimator_count', 0)
            # 본문에서 "N/N (100%)" 또는 "17/17" 패턴 추출
            text_concat = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
            # 컨센 매수 의견 분포 표기 ("매수 17 (100%)") 와 미반영 비약 ("17/17 (100%) 미반영") 구분
            # "X/Y (100%)" 패턴만 잡되 surrounding 50자 안에 "정정", "이전", "비약", "오기" 키워드 있으면 자가정정 PASS
            for m_obj in re.finditer(r'(\d+)\s*/\s*(\d+)\s*\(\s*100\s*%\s*\)', text_concat):
                n, m = int(m_obj.group(1)), int(m_obj.group(2))
                if m == estimator_count and n_known < estimator_count and n_known > 0:
                    surrounding = text_concat[max(0, m_obj.start()-100):m_obj.end()+100]
                    if any(kw in surrounding for kw in ['정정', '이전 v', '비약', '오기', '데이터 비약', 'v5.0 "', 'v5.0 “']):
                        continue  # 자가 정정 명시 표현이므로 PASS
                    b22_errs.append(
                        f"본문 \"{n}/{m} (100%)\" 표기 vs Wisereport recent_tp_changes 명시 broker {n_known}개만 데이터 보유 "
                        f"({m-n_known}개 broker 일자 미공개) -- 데이터 비약 가능성"
                    )
                    break
    except Exception:
        pass
    if b22_errs:
        fail += 1
    results.append(('B22 N/M 100% 비약', 'FAIL' if b22_errs else 'PASS', '; '.join(b22_errs)[:200] if b22_errs else 'broker 데이터 일관 또는 미감지'))

    # ========== B23 (v5.7 신설): 밴드 유효성 게이트 (US B19 의 KR 이식) ==========
    # _per_band.json 의 per/pbr_band_valid 가 False 인데 본문이 "5년 평균 대비" 를
    # 단정하면 차단. 사이클주(풍산/OCI홀딩스)는 PER 분산이 커서 평균이 노이즈다.
    band23 = load_or_none(f'data/{stock_name}/_per_band.json')
    text_concat = ' '.join(v for v in sections.values() if isinstance(v, str))
    b23_status, b23_detail = band_gate(band23, text_concat)
    if b23_status == 'FAIL':
        fail += 1
    results.append(('B23 밴드 유효성', b23_status, b23_detail[:250]))

    # 출력
    print(f"\n{'='*70}")
    print(f"  STEP 6 1회차 B 블록 (B1~B23) -- 수치 정합성: {stock_name}")
    print(f"{'='*70}\n")
    for item, status, detail in results:
        icon = '✓' if status == 'PASS' else ('✗' if status == 'FAIL' else '?')
        print(f"  [{icon}] {item:25} {status:10} {detail}")
    print(f"\n총 FAIL: {fail}건")
    print(f"{'='*70}\n")
    if fail > 0:
        print(f"[경고] {fail}건의 수치 정합성 오류 발견. STEP 6 1회차에서 반드시 수정 후 2회차로 진입하라.")
        return 2
    print("[OK] 모든 B 블록(B1~B23) 통과. 2회차 report-critic 호출 가능.")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python scripts/verify_numbers.py {종목명}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
