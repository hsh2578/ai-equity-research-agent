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
    's02_investment_points',
    's03_company_overview',
    's04_industry',
    's08_financial',
    's09_valuation',
    's13_thesis',
    's14_short_thesis',
]

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

    print(f"\n총 FAIL: {fail} / 전체 체크 {total_checks}")
    score = (1 - fail / total_checks) * 100 if total_checks else 0
    print(f"서술 품질 점수: {score:.0f}/100")
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
