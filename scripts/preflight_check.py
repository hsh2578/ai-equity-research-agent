"""
preflight_check.py -- analysis.json 작성 직후 의무 호출 사전 차단 검증 스크립트
v5.4 신설 (2026-05, 풍산 v1~v6 + 와이지엔터 v5.0~v5.1 + 대한항공 v3 사고 누적 후)

목적: 메인 에이전트가 작성 시점에 우회한 v5.4 1~7 절대 규칙을
      analysis.json + Peer/Wisereport/FnGuide 데이터와 1:1 자동 검증으로 강제.

차단 항목 (다음 종목에서 90%+ 사고 차단):
  C1. em-dash (—, U+2014) 자동 치환 (cp949 콘솔 에러 차단)
  C2. JSON control char (raw \\n /\\r/\\t in string) 자동 fix
  C3. Peer 시총 KIS 1:1 검증 (_peer_snapshot.json vs analysis.json.peers)
       - 시총 ±10% 차이 시 FAIL (JYP v1/대한항공 v3 재발 차단)
  C4. 컨센 일관성 (analysis.json "N개사" 표기 vs _wisereport.json estimator_count)
  C5. 시나리오 트리 ASCII (├─ │ └─ ─) 자동 감지 → 표 변환 권고
  C6. PER 시점 키워드 동행 검증 (PER 단독 표기 시 시점 키워드 동행 의무)
  C7. 컨센 평균 수치 잔재 grep (정정 누락 차단)
  C8. forward_per / opinion.target_base / opinion.rating 정합성

사용법:
    python scripts/preflight_check.py {종목명}

종료 코드:
    0 = 통과 (또는 자동 fix 후 통과) → STEP 5 진입 가능
    1 = 차단 (FAIL 1건+) → analysis.json 정정 후 재실행 의무
"""
import sys
import io
import os
import json
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def _load(path):
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding='utf-8'))
    except Exception:
        return None


def main(stock_name: str) -> int:
    print(f"\n{'='*70}\n  preflight_check (v5.4 신설): {stock_name}\n{'='*70}\n")

    analysis_path = f'scripts/analysis_{stock_name}.json'
    if not os.path.exists(analysis_path):
        print(f'[FAIL] {analysis_path} 부재')
        return 1

    # 원본 raw 읽기 (em-dash + control char fix용)
    with open(analysis_path, encoding='utf-8') as f:
        raw = f.read()

    fails = []
    fixes = []

    # ========== C1: em-dash 자동 치환 ==========
    em_count = raw.count(chr(0x2014)) + raw.count(chr(0x2013))
    if em_count > 0:
        raw = raw.replace(chr(0x2014), '--').replace(chr(0x2013), '-')
        fixes.append(f'C1: em-dash {em_count}건 자동 치환 (— → --, – → -)')

    # ========== C2: JSON control char (raw newline in string) 자동 fix ==========
    result = []
    in_string = False
    escape = False
    cc_count = 0
    for c in raw:
        if escape:
            result.append(c); escape = False; continue
        if c == '\\':
            result.append(c); escape = True; continue
        if c == '"':
            result.append(c); in_string = not in_string; continue
        if in_string and c == '\n':
            result.append('\\n'); cc_count += 1; continue
        if in_string and c == '\r':
            result.append('\\r'); cc_count += 1; continue
        if in_string and c == '\t':
            result.append('\\t'); cc_count += 1; continue
        result.append(c)
    raw_fixed = ''.join(result)
    if cc_count > 0:
        fixes.append(f'C2: JSON string 내 raw control char {cc_count}건 자동 escape')

    # 자동 fix 결과 저장
    if fixes:
        with open(analysis_path, 'w', encoding='utf-8') as f:
            f.write(raw_fixed)
        for fx in fixes:
            print(f'  [AUTO-FIX] {fx}')
        print()

    # JSON 파싱 (fix 후)
    try:
        d = json.loads(raw_fixed)
    except json.JSONDecodeError as e:
        print(f'[FAIL] C0: JSON 파싱 실패 ({e}). 자동 fix 한계 -- 수동 정정 필요')
        return 1

    # ========== C3: Peer 시총 KIS 1:1 검증 ==========
    peer_path = f'data/{stock_name}/_peer_snapshot.json'
    peers_json = d.get('peers', [])
    peer_snap = _load(peer_path)
    if peer_snap and peers_json:
        for p in peers_json:
            if p.get('highlight'):
                continue  # 본 종목 제외
            name = p.get('name', '')
            mc_str = str(p.get('market_cap', ''))
            # "9.7조" → 97000억 / "0.44조" → 4400억 / "1.0조" → 10000억
            m_jo = re.match(r'([\d.]+)\s*조', mc_str)
            m_uk = re.match(r'([\d,]+)\s*억', mc_str)
            mc_uk = None
            if m_jo:
                mc_uk = int(float(m_jo.group(1)) * 10000)
            elif m_uk:
                mc_uk = int(m_uk.group(1).replace(',', ''))
            if mc_uk is None:
                continue
            snap = peer_snap.get(name)
            if not snap:
                fails.append(f'C3 Peer "{name}" -- _peer_snapshot.json 부재 (KIS 실시간 미조회)')
                continue
            kis_uk = snap.get('market_cap_uk', 0)
            if kis_uk == 0:
                continue
            diff = abs(mc_uk - kis_uk) / kis_uk * 100
            if diff > 10:
                fails.append(f'C3 Peer "{name}" 시총 불일치 -- analysis={mc_uk:,}억 vs KIS={kis_uk:,}억 (차이 {diff:.0f}%) -- JYP v1/대한항공 v3 재발')
            # PER 부호 검증 (적자 음수 vs 양수 추정)
            kis_per = snap.get('per', 0)
            json_per = p.get('per', 0)
            if isinstance(json_per, (int, float)) and kis_per < 0 and json_per > 0:
                fails.append(f'C3 Peer "{name}" PER 부호 오류 -- analysis={json_per} (양수 추정) vs KIS={kis_per} (실제 적자)')

    # ========== C4: 컨센 일관성 (Wisereport estimator_count) ==========
    wr_path = f'data/{stock_name}/_wisereport.json'
    wr = _load(wr_path)
    if wr:
        wr_count = (wr.get('consensus', {}) or {}).get('estimator_count', 0)
        wr_avg_tp = (wr.get('consensus', {}) or {}).get('avg_target_price', 0)
        text_all = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
        # "N개사" 패턴 추출
        nps = re.findall(r'(\d+)개사', text_all)
        if wr_count and nps:
            mismatch = [int(n) for n in nps if int(n) != wr_count and int(n) > 5]
            if mismatch:
                fails.append(f'C4 컨센 추정기관 수 불일치 -- 본문 {set(mismatch)} vs Wisereport {wr_count}개사')
        if wr_avg_tp:
            tp_str = f'{wr_avg_tp:,}'
            if tp_str not in text_all and str(wr_avg_tp) not in text_all:
                fails.append(f'C4 Wisereport 평균 목표가 {tp_str}원 본문 미인용 (잔재 정정 누락 가능성)')

    # ========== C5: 시나리오 트리 ASCII 감지 ==========
    text_all = ' '.join(v for v in d.get('sections', {}).values() if isinstance(v, str))
    ascii_tree_chars = ['├─', '└─', '│  ', '─┤']
    ascii_count = sum(text_all.count(ch) for ch in ascii_tree_chars)
    if ascii_count > 0:
        fails.append(f'C5 시나리오 트리 ASCII ({ascii_count}건) -- 표 형식으로 변환 의무 (PDF 폰트 깨짐 위험)')

    # ========== C6: PER 시점 키워드 동행 검증 ==========
    # "PER" 등장 시 ±30자 안에 시점 키워드 동행 의무
    time_kws = ['후행', 'TTM', 'Forward', '12M', '연간', '업종', 'PER (TTM)',
                '2024E', '2025', '2026E', '2027E', '2028E', '5Y', 'Target', '평균', '컨센', '실측', '+1σ', '-1σ', '+0', '-0', '+1', '-1']
    per_pattern = re.finditer(r'\bPER\s*(\d+\.?\d*)', text_all)
    bare_per = []
    for m in per_pattern:
        ctx = text_all[max(0, m.start()-30):m.end()+30]
        if not any(kw in ctx for kw in time_kws):
            bare_per.append(m.group(0))
    if len(bare_per) > 3:
        fails.append(f'C6 PER 단독 표기 {len(bare_per)}건 (시점 키워드 동행 부재) -- 풍산 v5 PER 혼용 사고 패턴')

    # ========== C7: 정정 잔재 grep (FnGuide 컨센 vs 본문) ==========
    # forward_per 정합 검증
    fp = (d.get('price', {}) or {}).get('forward_per', 0)
    if fp:
        # 본문에 fp 값 등장 의무
        if str(fp) not in text_all:
            fails.append(f'C7 forward_per {fp} -- 본문 미등장 (price 객체와 본문 불일치)')

    # ========== C8: opinion 정합성 ==========
    opinion = d.get('opinion', {})
    rating = opinion.get('rating', '')
    if rating:
        if rating not in text_all and rating not in ['BUY', 'HOLD', 'SELL']:
            fails.append(f'C8 opinion.rating "{rating}" 본문 미등장')
        # 적정주가 양수 + 일관성
        for k in ['target_bear', 'target_base', 'target_bull']:
            v = opinion.get(k, 0)
            if v <= 0:
                fails.append(f'C8 {k}={v} -- 양수 의무')
        bear, base, bull = opinion.get('target_bear', 0), opinion.get('target_base', 0), opinion.get('target_bull', 0)
        if bear and base and bull:
            if not (bear < base < bull):
                fails.append(f'C8 Bear({bear}) < Base({base}) < Bull({bull}) 순서 위반')

    # ========== 출력 ==========
    print(f'\n{"="*70}')
    if not fails:
        print(f'[OK] preflight 통과 ({len(fixes)}건 자동 fix). STEP 5 진입 가능.')
        if fixes:
            for fx in fixes:
                print(f'  - {fx}')
        return 0

    print(f'[FAIL] preflight 차단 -- {len(fails)}건 FAIL. STEP 5 진입 불가.')
    print()
    for i, f in enumerate(fails, 1):
        print(f'  {i}. {f}')
    print()
    print('정정 후 재실행: python scripts/preflight_check.py {stock_name}')
    print(f'{"="*70}\n')
    return 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/preflight_check.py {종목명}')
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
