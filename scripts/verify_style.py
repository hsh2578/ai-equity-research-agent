"""
STEP 6 1회차 C 블록 -- 서술 품질 자동 검증 (v4.9 신설)

검증 항목:
    C1. 불릿 비율 < 30%
    C2. 전문용어 풀어쓰기 (OPM/EBITDA/HBM/WACC/PMI 등)
    C3. 소제목 메시지성 (단순 라벨 금지)
    C4. 서술 톤 (~것으로 보인다/추정된다 금지)
    C5. 3요소 밀도 (숫자 + 따라서/결과적으로 키워드)
    C6. 자연어 비중 > 60%

사용법:
    python scripts/verify_style.py {종목명}
"""
import json
import sys
import io
import re

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


TARGET_SECTIONS = [
    's01_opinion',  # v4.16: s01도 톤 검증 대상에 추가
    's02_investment_points',
    's03_company_overview',
    's04_industry',
    's08_financial',
    's09_valuation',
    's13_thesis',
    's14_short_thesis',
]

# v4.16: 위트성 인용 박스 권장 섹션
WITTY_QUOTE_RECOMMENDED = ['s01_opinion', 's13_thesis', 's14_short_thesis']

TECHNICAL_TERMS = {
    'OPM': '영업이익률',
    'EBITDA': '감가상각 전 영업현금',
    'EBIT': '이자·세금 차감 전 이익',
    'ROE': '자기자본이익률',
    'ROIC': '투하자본수익률',
    'PMI': '인수합병 후 통합',
    'WACC': '가중평균자본비용',
    'DCF': '현금흐름할인',
    'SOTP': '사업부별 합산',
    'NAV': '순자산가치',
    'FCF': '자유현금흐름',
    'EV/EBITDA': '기업가치 대비 현금창출력',
    'PSR': '주가매출비율',
    'HBM': '고대역폭 메모리',
    'DDR': 'Dynamic Random Access Memory',
    'CAGR': '연평균 성장률',
    'HEV': '하이브리드 전기차',
    'BEV': '순수 전기차',
    'M/S': '시장점유율',
    'ASP': '평균판매단가',
    'CapEx': '자본적 지출',
    'OCF': '영업활동현금흐름',
}

# 금지 표현 -- "것으로 보인다" 등 비확신 톤
BANNED_PATTERNS = [
    r'것으로\s?보인다',
    r'것으로\s?추정된다',
    r'할\s?수도\s?있다',
    r'할\s?수\s?있을\s?것으로',
    r'할\s?것으로\s?보인다',
]

# 3요소 시사점 키워드
TRANSITION_KEYWORDS = ['따라서', '결과적으로', '시사점', '의미한다', '즉', '이는', '왜냐하면', '이로써', '한편', '반면']


def section_body(sections, key):
    v = sections.get(key, '')
    if isinstance(v, str):
        return v
    return ''


def check_c1_bullet_ratio(text):
    """C1: 불릿 줄 / 전체 줄 < 30%"""
    lines = [l for l in text.split('\n') if l.strip()]
    if not lines:
        return None, 0
    bullet_lines = sum(1 for l in lines if re.match(r'^\s*[-*]\s', l))
    # 테이블 / 코드 제외
    non_table = [l for l in lines if not l.strip().startswith('|') and not l.strip().startswith('```')]
    if not non_table:
        return None, 0
    bullet_in_non_table = sum(1 for l in non_table if re.match(r'^\s*[-*]\s', l))
    ratio = bullet_in_non_table / len(non_table) * 100
    return ratio, bullet_in_non_table


def check_c2_term_explained(text):
    """C2: 전문용어 첫 등장 시 괄호 풀이 존재"""
    missing = []
    for term in TECHNICAL_TERMS:
        if term in text:
            # term 이 처음 등장하는 위치의 앞뒤 60자 스캔
            idx = text.find(term)
            # 이후 "(" 가 60자 이내에 있고 한글 설명이 있는지
            tail = text[idx: idx + 80]
            has_explanation = '(' in tail and ')' in tail
            # 또는 별도 용어 풀이 섹션이 있는지 (예: "OPM(영업이익률)")
            if not has_explanation:
                missing.append(term)
    return missing


def check_c3_heading_message(text):
    """C3: ### 소제목이 15자+ 이면서 의미있는 문장형인지"""
    headings = re.findall(r'^#{2,4}\s+(.+)$', text, re.M)
    if not headings:
        return None, []
    weak = []
    for h in headings:
        h = h.strip()
        # 매우 짧거나 (< 10자) 단순 라벨 패턴이면 weak
        if len(h) < 10 and not any(c in h for c in ['--', '—', ':', '?']):
            weak.append(h)
    return len(weak) / len(headings) * 100, weak


def check_c4_tone(text):
    """C4: 금지 톤 패턴 검출"""
    hits = []
    for pat in BANNED_PATTERNS:
        for m in re.finditer(pat, text):
            hits.append(m.group(0))
    return hits


def check_c5_three_element_density(text):
    """C5: 섹션당 숫자 3개+ + 시사점 키워드 2개+"""
    numbers = re.findall(r'\d+\.?\d*(?:조|억|%|원|배|x|σ)', text)
    transitions = sum(text.count(kw) for kw in TRANSITION_KEYWORDS)
    return len(numbers), transitions


def check_c6_prose_ratio(text):
    """C6: 자연어 비중 (테이블/코드 제외한 문장 길이)"""
    total_chars = len(text)
    # 테이블 행 (|로 시작) 제거
    prose = re.sub(r'^\|.*$', '', text, flags=re.M)
    # 코드 블록 제거
    prose = re.sub(r'```[\s\S]*?```', '', prose)
    prose_chars = len(prose.strip())
    return prose_chars / total_chars * 100 if total_chars else 0


# v4.16 톤 변환 검증 (C7~C10)

def check_c7_short_subtitle(text):
    """C7 (v4.16 + v4.18): 소제목 한 줄 + 15자 이내 위트 (### 단계)
    - 라벨형 ("투자포인트", "재무 분석") 금지
    - v4.18: "포인트 1. K방산 수주잔고..." 같은 라벨+세부 결합형 (45자+) 강화 감지
    - "광고는 더블링, 안전마진은 제로" 같은 메시지+위트형 권장
    """
    headings = re.findall(r'^(#{2,4})\s+(.+)$', text, flags=re.M)
    if not headings:
        return None, []
    label_pattern = re.compile(r'^(투자\s?의견|투자\s?포인트|재무\s?분석|밸류\s?에이션|회사\s?개요|산업.{0,3}시장|경쟁\s?구도|경제적\s?해자|경영진|매크로\s?리스크|카탈리스트|시나리오|투자\s?논문|숏\s?논거|실적|컨센서스|수급\s?분석|주주환원|실행\s?계획|신뢰도)\s*$')
    # v4.18: 라벨+세부 결합형 ("포인트 1. ..." / "숏 논거 N. ..." / "약세 N. ...")
    label_combo = re.compile(r'^(포인트|숏\s?논거|약세\s?\d|강세\s?\d|시나리오\s?\d|반박\s?\d)\s*\d*\.\s+\S+')
    weak = []
    for level, title in headings:
        title_s = title.strip()
        # 단순 라벨형
        if label_pattern.match(title_s):
            weak.append(title_s[:25])
        # v4.18: 라벨+세부 결합형이고 30자+ 이면 weak (위트+부제 분리 권장)
        elif label_combo.match(title_s) and len(title_s) > 30:
            weak.append(f"{title_s[:25]}... ({len(title_s)}자, 위트+부제 분리 권장)")
        elif len(title_s) > 40:
            weak.append(f"{title_s[:20]}... ({len(title_s)}자)")
    return len(weak) / len(headings) * 100, weak


def check_c8_english_directs(text):
    """C8 (v4.16): 영문 직역체 표기 검출
    - $1.5B, $9.13B, 4.22B 같은 영문 단위 직접 표기 카운트
    - 한글로 변환된 "15억 달러", "42.2억 주" 권장
    """
    # $X.XB / $X.XT / X.XB 형태 (단, 표/코드 제외)
    prose = re.sub(r'\|.*?\|', '', text)  # 표 제거
    prose = re.sub(r'```[\s\S]*?```', '', prose)
    # $XX.XB 또는 XX.XB shares
    en_units = re.findall(r'\$\d+\.?\d*[BMT]\b|\d+\.?\d*\s?[BM]\s+(?:주|shares)', prose)
    return len(en_units), en_units[:5]


def check_c9_long_sentence(text):
    """C9 (v4.16): 한 문장 100자+ 비율 (영문 직역체 신호)
    - 자연 한국어는 50자 이내 호흡
    """
    # 표/코드 제거
    prose = re.sub(r'\|.*?\|', '', text)
    prose = re.sub(r'```[\s\S]*?```', '', prose)
    # 마침표/물음표/느낌표/콜론으로 문장 분리
    sentences = re.split(r'[.!?]\s+|[다요]\.\s+', prose)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    if not sentences:
        return 0, 0
    long_sentences = [s for s in sentences if len(s) > 100]
    return len(long_sentences) / len(sentences) * 100, len(long_sentences)


def check_c10_witty_quote(text):
    """C10 (v4.16, v4.18 의무화): 위트성 마무리 인용 박스 (>) 존재 여부
    - "> 가입자는 끝, 광고가 시작 -- 그러나 시장이 한 발 빨랐다." 패턴
    - v4.18: s01/s13/s14 모두 강제 (한화에어로 v1: s01/s14 누락 사고 방지)
    """
    quotes = re.findall(r'^>\s*(.+)$', text, flags=re.M)
    return len(quotes), [q.strip()[:50] for q in quotes[:2]]


def check_c11_one_line_review(text):
    """C11 (v4.20 신설 -- 에스엠 v1 한 줄 평가 47자 사고 방지):
    "한 줄 평가:" 패턴 검출 시 콜론 뒤 30자 이내 강제.
    - 위반 예: "4Q25 한 줄 평가: 어닝은 비트, 컨센은 줄하향 -- 시장은 음반을 버리고 있다." (콜론 뒤 39자)
    - 권장 예: "Q1 FY26 한 줄 평가: 광고는 진짜다." (콜론 뒤 11자)
    """
    pattern = re.compile(r'한\s?줄\s?평가\s*:\s*([^\n]+)', re.M)
    over = []
    total = 0
    for m in pattern.finditer(text):
        total += 1
        body = m.group(1).strip()
        # 마침표 이전까지가 첫 문장
        first_sent = re.split(r'[.!?]', body)[0].strip()
        if len(first_sent) > 30:
            over.append(f"{first_sent[:25]}... ({len(first_sent)}자)")
    return total, over


def check_c12_zscore_std_guard(text, stock_name):
    """C12 (v4.20 신설 -- 에스엠 v1 PBR z=-3.57σ 통계 신뢰도 사고 방지):
    표준편차 < 0.5 인데 |z-score| > 2.5 인 경우 "정상화/일회성/주의" 키워드 매칭 검증.
    - _per_band.json 의 표준편차를 직접 참조
    - 본문에 "z-score" 또는 "σ" 표기 검출 시 std 임계값 가드
    """
    band_path = f'data/{stock_name}/_per_band.json'
    try:
        band = json.load(open(band_path, encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return None, []

    pbr_std = band.get('pbr_std') or 0
    per_std = band.get('per_std') or 0
    pbr_z = band.get('current_pbr_z') or 0
    per_z = band.get('current_per_z') or 0

    flags = []
    # PBR std < 0.5 + |z| > 2.5 인 경우
    if pbr_std and pbr_std < 0.5 and abs(pbr_z) > 2.5:
        # 본문에 "정상화/일회성/주의/표준편차/한정/제한" 키워드 매칭
        guard_kws = ['정상화', '일회성', '주의', '표준편차', '한정', '제한', '신뢰도', 'BPS 폭증', 'BPS 일회성']
        if not any(kw in text for kw in guard_kws):
            flags.append(
                f"PBR std={pbr_std:.2f}(매우 작음) + z={pbr_z:.2f}σ(극단) -- 정상화/일회성 가드 키워드 누락"
            )
    if per_std and per_std < 0.5 and abs(per_z) > 2.5:
        guard_kws = ['정상화', '일회성', '주의', '표준편차', '한정', '제한', '신뢰도', 'TTM']
        if not any(kw in text for kw in guard_kws):
            flags.append(
                f"PER std={per_std:.2f}(매우 작음) + z={per_z:.2f}σ(극단) -- 가드 키워드 누락"
            )
    return (pbr_std, per_std, pbr_z, per_z), flags


def main(stock_name):
    path = f'scripts/analysis_{stock_name}.json'
    try:
        d = json.load(open(path, encoding='utf-8'))
    except FileNotFoundError:
        print(f'[ERR] {path} 없음')
        return 1

    sections = d.get('sections', {})
    print(f"\n{'='*70}")
    print(f"  STEP 6 1회차 C 블록 -- 서술 품질 자동 검증: {stock_name}")
    print(f"{'='*70}\n")

    fail = 0
    total_checks = 0

    for key in TARGET_SECTIONS:
        text = section_body(sections, key)
        if not text:
            print(f"  [{'SKIP':6}] {key:26} (빈 섹션)")
            continue

        # C1: 불릿 비율
        ratio, n = check_c1_bullet_ratio(text)
        if ratio is not None:
            total_checks += 1
            ok = ratio < 30
            icon = '✓' if ok else '✗'
            if not ok:
                fail += 1
            print(f"  [{icon} C1] {key:26} 불릿 {ratio:.0f}% ({n}줄)  {'' if ok else '← 30%+ 과다'}")

        # C2: 전문용어 풀이
        missing = check_c2_term_explained(text)
        total_checks += 1
        ok = len(missing) <= 1  # 1개까지 허용
        icon = '✓' if ok else '✗'
        if not ok:
            fail += 1
        print(f"  [{icon} C2] {key:26} 미풀이 용어 {len(missing)}개  {missing[:3] if missing else ''}")

        # C3: 소제목 메시지성
        pct, weak = check_c3_heading_message(text)
        if pct is not None:
            total_checks += 1
            ok = pct < 50
            icon = '✓' if ok else '✗'
            if not ok:
                fail += 1
            print(f"  [{icon} C3] {key:26} 짧은 소제목 {pct:.0f}%  {weak[:2] if weak else ''}")

        # C4: 금지 톤
        hits = check_c4_tone(text)
        total_checks += 1
        ok = len(hits) == 0
        icon = '✓' if ok else '✗'
        if not ok:
            fail += 1
        print(f"  [{icon} C4] {key:26} 비확신 표현 {len(hits)}개  {hits[:3] if hits else ''}")

        # C5: 3요소
        nums, trans = check_c5_three_element_density(text)
        total_checks += 1
        ok = nums >= 3 and trans >= 2
        icon = '✓' if ok else '✗'
        if not ok:
            fail += 1
        print(f"  [{icon} C5] {key:26} 숫자 {nums}개 / 시사점 {trans}개  {'' if ok else '← 숫자 3+ 시사점 2+ 필요'}")

        # C6: 자연어 비중
        ratio6 = check_c6_prose_ratio(text)
        total_checks += 1
        ok = ratio6 >= 60
        icon = '✓' if ok else '✗'
        if not ok:
            fail += 1
        print(f"  [{icon} C6] {key:26} 자연어 {ratio6:.0f}%  {'' if ok else '← 60%+ 필요 (테이블 과다)'}")

        # ===== v4.16 톤 변환 검증 (C7~C10) =====

        # C7: 소제목 메시지성 + 길이 (v4.16: 라벨형 금지 + 40자+ 금지)
        weak_pct, weak_titles = check_c7_short_subtitle(text)
        if weak_pct is not None:
            total_checks += 1
            ok = weak_pct < 40  # 40% 이상이 라벨/긴 소제목이면 FAIL
            icon = '✓' if ok else '✗'
            if not ok:
                fail += 1
            print(f"  [{icon} C7] {key:26} 라벨/긴 소제목 {weak_pct:.0f}%  {weak_titles[:2] if weak_titles else ''}")

        # C8: 영문 직역체 ($1.5B, 4.22B shares 직접 표기)
        en_count, en_examples = check_c8_english_directs(text)
        total_checks += 1
        ok = en_count <= 5  # 표 제외 본문 5개까지 허용
        icon = '✓' if ok else '✗'
        if not ok:
            fail += 1
        print(f"  [{icon} C8] {key:26} 영문 직역 표기 {en_count}개  {en_examples[:3] if en_examples else ''} {'← 한글 표기 권장 (X억 달러 등)' if not ok else ''}")

        # C9: 한 문장 100자+ 비율 (영문 직역체 신호)
        long_pct, long_count = check_c9_long_sentence(text)
        total_checks += 1
        ok = long_pct < 25  # 25% 이상 긴 문장이면 호흡 부족
        icon = '✓' if ok else '✗'
        if not ok:
            fail += 1
        print(f"  [{icon} C9] {key:26} 100자+ 문장 {long_pct:.0f}% ({long_count}개)  {'← 50자 이내 호흡 권장' if not ok else ''}")

        # C10: 위트성 인용 박스 (s01/s13/s14 권장)
        if key in WITTY_QUOTE_RECOMMENDED:
            quote_count, quote_examples = check_c10_witty_quote(text)
            total_checks += 1
            ok = quote_count >= 1
            icon = '✓' if ok else '✗'
            if not ok:
                fail += 1
            print(f"  [{icon} C10] {key:26} 위트 인용 박스 {quote_count}개  {quote_examples[:1] if quote_examples else ''} {'← > 한 줄 결론 권장' if not ok else ''}")

        # C11 (v4.20): "한 줄 평가:" 콜론 뒤 30자 이내 (s01/s08/s15 주로 적용)
        c11_total, c11_over = check_c11_one_line_review(text)
        if c11_total > 0:
            total_checks += 1
            ok = len(c11_over) == 0
            icon = '✓' if ok else '✗'
            if not ok:
                fail += 1
            print(f"  [{icon} C11] {key:26} 한 줄 평가 30자+: {len(c11_over)}/{c11_total}개  {c11_over[:1] if c11_over else ''} {'← 콜론 뒤 30자 이내 강제' if not ok else ''}")

        # C12 (v4.20): PBR/PER std<0.5 + |z|>2.5 인데 가드 키워드 누락 검증 (s09 주로 적용)
        c12_meta, c12_flags = check_c12_zscore_std_guard(text, stock_name)
        if c12_meta is not None and c12_flags:
            total_checks += 1
            ok = False
            icon = '✗'
            fail += 1
            print(f"  [{icon} C12] {key:26} z-score 가드 누락: {len(c12_flags)}건  {c12_flags[:1]} ← BPS/EPS 일회성 효과 별도 주석 필수")

    # ========== v5.0 신설: C13~C16 (1티어 애널리스트 서술 12원칙) ==========
    import re as _re5
    v5_targets = ['s02_thesis_catalysts', 's02_investment_points', 's04_industry',
                  's04_industry_competition', 's06_financial', 's07_financial_analysis',
                  's08_financial', 's09_scenarios_risks', 's10_macro', 's12_scenarios']
    v5_text = '\n'.join(
        sections.get(k, '') for k in v5_targets if sections.get(k)
    )
    if v5_text:
        # ----- C13. 결론 선행 박스 -----
        first_5000 = v5_text[:5000]
        c13_patterns = [r'한\s*줄\s*평가\s*:', r'Q\d\s*FY\s*\d+\s*한\s*줄\s*평가',
                        r'\d+Q\d+\s+Review\s*:', r'결론\s*선행\s*:']
        c13_hits = sum(1 for p in c13_patterns if _re5.search(p, first_5000))
        total_checks += 1
        if c13_hits == 0:
            fail += 1
            print(f"  [✗ C13] 결론 선행 박스           누락 -- 섹션 첫 문단에 \"한 줄 평가:\" 또는 Review 박스 의무 (임소정/최정욱)")
        else:
            print(f"  [✓ C13] 결론 선행 박스           {c13_hits}건")

        # ----- C14. 비교 벤치마크 밀도 -----
        c14_hits = (
            len(_re5.findall(r'반면\s+', v5_text)) +
            len(_re5.findall(r'대비\s+[\d+\-]', v5_text)) +
            len(_re5.findall(r'\(.+\)\s*대비', v5_text))
        )
        total_checks += 1
        if c14_hits < 5:
            fail += 1
            print(f"  [✗ C14] 비교 벤치마크 밀도        {c14_hits}개 (5개+ 권장) -- \"반면 ~\"/\"X 대비 Y\" 대비 구조 부족 (최정욱)")
        else:
            print(f"  [✓ C14] 비교 벤치마크 밀도        {c14_hits}개")

        # ----- C15. 5단 메커니즘 -----
        arrow_count = v5_text.count('→')
        mechanism_keywords = ['병목', '메커니즘', '수혜', '해결책', '구조적', '미반영']
        mech_hits = sum(1 for k in mechanism_keywords if k in v5_text)
        total_checks += 1
        if arrow_count < 4 or mech_hits < 3:
            fail += 1
            print(f"  [✗ C15] 5단 메커니즘             화살표 {arrow_count}/키워드 {mech_hits} (4+/3+ 권장) -- 박상욱 패턴 부족")
        else:
            print(f"  [✓ C15] 5단 메커니즘             화살표 {arrow_count}/키워드 {mech_hits}")

        # ----- C16. Before/After 조 단위 -----
        before_after = _re5.findall(r'[\d.]+조\s*(?:원)?\s*[→]\s*[+\-]?[\d.]+조', v5_text)
        if len(before_after) >= 1:
            total_checks += 1
            if len(before_after) < 3:
                fail += 1
                print(f"  [✗ C16] Before/After 조 대비    {len(before_after)}건 (3+ 권장 다사업부) -- 임소정 패턴")
            else:
                print(f"  [✓ C16] Before/After 조 대비    {len(before_after)}건")

    # ========== v5.4 신설: C17~C20 (포장 서술 자동 차단) ==========
    # 풍산/대한항공 사고 후 -- "수치 + 출처 + 델타" 좋은 패턴 vs "양호한/우수한/긍정적인" 포장 차단
    full_text = '\n'.join(v for v in d.get('sections', {}).values() if isinstance(v, str))

    # ----- C17. 모호 형용사 (수치 없는 포장) -----
    total_checks += 1
    pkg_adj = ['매우 우수', '양호한 수준', '우수한 수준', '긍정적인 흐름', '안정적인 흐름',
               '견조한 흐름', '호조세', '확고한 위치', '뛰어난 성과', '꾸준한 성장',
               '큰 폭의 개선', '주목할 만한', '관심을 가져볼', '관심이 필요']
    pkg_count = sum(full_text.count(kw) for kw in pkg_adj)
    if pkg_count >= 5:
        fail += 1
        print(f"  [✗ C17] 모호 형용사 (포장 서술)  {pkg_count}건 (5건 이상 = 포장) -- '매우 우수/양호한 수준/긍정적 흐름' 등 수치 없는 표현 다수")
    else:
        print(f"  [✓ C17] 모호 형용사               {pkg_count}건 (5건 미만)")

    # ----- C18. 비확신 + 수치 부재 결합 (포장 시그널) -----
    total_checks += 1
    # "예상된다/추정된다/할 것으로/할 수 있다" + 같은 문장 내 숫자 부재
    sentences = _re5.split(r'[.!?]\s+', full_text)
    weak_pkg = 0
    weak_examples = []
    for s in sentences:
        if len(s) < 20:
            continue
        # 비확신 어미 또는 모호 표현
        if _re5.search(r'(예상된다|예상됨|추정된다|보인다|할 수 있다|할 것으로 보|할 것으로 예상|기대된다|것으로 판단)', s):
            # 같은 문장 내 숫자 부재 (% 또는 억/조/원 같은 단위 없음)
            if not _re5.search(r'\d+\.?\d*\s*(%|억|조|원|배|만|천|p|bp|x)', s):
                weak_pkg += 1
                if len(weak_examples) < 3:
                    weak_examples.append(s.strip()[:80])
    if weak_pkg >= 5:
        fail += 1
        print(f"  [✗ C18] 비확신+수치부재 결합     {weak_pkg}건 (5건 이상 = 포장) -- '예상된다/추정된다 + 수치 0' 패턴")
        for ex in weak_examples:
            print(f"       예: \"{ex}...\"")
    else:
        print(f"  [✓ C18] 비확신+수치부재 결합     {weak_pkg}건 (5건 미만)")

    # ----- C19. 좋은 패턴 (수치 + 출처 + 델타) 밀도 -----
    total_checks += 1
    # "+X% YoY" 또는 "+X억 (+Y%)" 또는 "X → Y" 패턴 (델타 명시)
    delta_patterns = [
        r'[+\-]\d+\.?\d*\s*%\s*(?:YoY|QoQ|전년|YTD)',
        r'[+\-]\d+\.?\d*\s*%p',
        r'\d+\.?\d*\s*(?:억|조|원|배)\s*\(\s*[+\-]\d+\.?\d*\s*%',
        r'\d+\.?\d*\s*[→→]\s*\d+\.?\d*\s*(?:억|조|원|%|배|x)',
        r'컨센\s*[+\-]\d+\.?\d*\s*%\s*(?:Beat|Miss|상회|미달)',
    ]
    delta_count = sum(len(_re5.findall(p, full_text)) for p in delta_patterns)
    if delta_count < 30:
        fail += 1
        print(f"  [✗ C19] 좋은 패턴 (수치+델타+출처) {delta_count}건 (30+ 권장) -- '+X% YoY' / 'A → B' / '컨센 +X% Beat' 등 부족")
    else:
        print(f"  [✓ C19] 좋은 패턴 밀도            {delta_count}건")

    # ----- C20. 클리셰 (산업 일반론 + 메커니즘 부재) -----
    total_checks += 1
    cliches = [
        'AI가 성장하면서', '글로벌 시장 확대', '구조적 성장 동력', '4차 산업혁명',
        '디지털 전환의 가속', '뉴노멀', '거대한 흐름', '미래 먹거리', '게임 체인저',
        '큰 변화의 시기', '패러다임 전환'
    ]
    cliche_count = sum(full_text.count(c) for c in cliches)
    if cliche_count >= 3:
        fail += 1
        print(f"  [✗ C20] 클리셰 (메커니즘 부재)    {cliche_count}건 (3건 이상 = 일반론) -- 박상욱 5단 메커니즘으로 대체")
    else:
        print(f"  [✓ C20] 클리셰                   {cliche_count}건")

    print(f"\n총 FAIL: {fail} / 전체 체크 {total_checks}")
    score = (1 - fail / total_checks) * 100 if total_checks else 0
    print(f"서술 품질 점수 (v5.0 C13~C16 + v5.4 C17~C20 포함): {score:.0f}/100")
    print(f"{'='*70}\n")

    if fail == 0:
        print("[OK] 서술 품질 통과. 2회차 report-critic 호출 가능.")
        return 0
    if score < 70:
        print(f"[경고] 서술 품질 {score:.0f}점 -- 70점 미달. 재작성 권고.")
        return 2
    print(f"[부분 통과] {score:.0f}점. 주요 FAIL 항목 수정 후 2회차 진입.")
    return 1


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("사용법: python scripts/verify_style.py {종목명}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
