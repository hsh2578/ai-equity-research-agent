"""
STEP 6 1회차 B 블록 -- 수치 정합성 자동 검증 스크립트 (v4.5 신설)

사용법:
    python scripts/verify_numbers.py {종목명}

출력: B1~B10 10개 항목 PASS/FAIL + 구체적 원인.
삼성전자 v1의 13건 사고 중 8건을 사전 차단 목적.
"""
import json
import sys
import io
import os
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


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

    # 출력
    print(f"\n{'='*70}")
    print(f"  STEP 6 1회차 B 블록 -- 수치 정합성 검증: {stock_name}")
    print(f"{'='*70}\n")
    for item, status, detail in results:
        icon = '✓' if status == 'PASS' else ('✗' if status == 'FAIL' else '?')
        print(f"  [{icon}] {item:25} {status:10} {detail}")
    print(f"\n총 FAIL: {fail}건")
    print(f"{'='*70}\n")
    if fail > 0:
        print(f"[경고] {fail}건의 수치 정합성 오류 발견. STEP 6 1회차에서 반드시 수정 후 2회차로 진입하라.")
        return 2
    print("[OK] 모든 B 블록 통과. 2회차 report-critic 호출 가능.")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python scripts/verify_numbers.py {종목명}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
