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


# 문장 끝 마침표 뒤에 올 수 있는 닫는 마크업/문장부호.
# 한국어 리포트는 "**...했다.**" 처럼 강조 문장을 자주 쓰는데, 이걸 경계로
# 인식하지 못하면 두 문장이 한 문장(100자+)으로 세어진다.
_SENT_CLOSERS = '*`)]"' + "'" + '\u201d\u2019'
_SENT_SPLIT = re.compile('[.!?][' + re.escape(_SENT_CLOSERS) + ']*\\s+|\\n+')


def split_sentences(text, min_len=20):
    """마크다운 산문을 문장 단위로 자른다.

    기존 구현은 `[.!?]\\s+|[다요]\\.\\s+` 만 썼고 두 가지를 못 쪼갰다.

    1. **줄바꿈**. 마크다운 리스트 항목·헤딩·출처줄이 각각 독립 단위인데
       분리자에 개행이 없어 통째로 한 "문장" 이 됐다.
    2. **닫는 마크업 뒤 마침표**. "**...벌어졌다.** 당기손익-..." 에서
       `다.` 뒤가 공백이 아니라 `**` 라 경계로 인식되지 않았다.

    실측(2026-09-08, 3종목 15개 섹션): 100자+ 문장 **60개 -> 30개**.
    C9 실패의 절반이 서술 문제가 아니라 계측 문제였다.
    이 게이트의 취지는 영문 직역체(진짜 긴 문장)를 잡는 것이지
    마크다운 구조를 문장으로 세는 것이 아니다.
    """
    return [x.strip() for x in _SENT_SPLIT.split(text or '') if len(x.strip()) > min_len]


def check_c9_long_sentence(text):
    """C9 (v4.16): 한 문장 100자+ 비율 (영문 직역체 신호)
    - 자연 한국어는 50자 이내 호흡
    """
    # 표/코드 제거
    prose = re.sub(r'\|.*?\|', '', text)
    prose = re.sub(r'```[\s\S]*?```', '', prose)
    sentences = split_sentences(prose)
    if not sentences:
        return 0, 0
    long_sentences = [x for x in sentences if len(x) > 100]
    return len(long_sentences) / len(sentences) * 100, len(long_sentences)



# ============================================================
# C21 / C22 (v5.7 신설) -- 스토리텔링 비중 게이트
#
# 배경(2026-09-08 사용자 지적 + 3종목 실측):
#   "산업분석·기업분석·투자포인트가 가장 중요한데 재무분석 위주로 쓰이면 별로다.
#    회사의 상태와 미래 비전, 어떤 이슈가 있는지가 중요하다. 메인은 스토리텔링이다."
#
#   실측: 가장 중요하다는 산업분석이 가이드 대비 74~110% 로 가장 미달이고
#   재무(119~137%)·밸류(132~147%)만 초과했다. 표 비중도 재무 46~57% 로
#   시나리오 섹션(19~21%) 의 두 배 이상이었다.
#
#   리포트는 재무제표 요약이 아니라 "이 회사가 어디로 가는가" 를 말하는 글이다.
#   숫자는 그 주장의 근거이지 글 자체가 아니다.
# ============================================================

# verify_style 은 구 v5.1 스킴 키를 읽어 왔다 (CLAUDE.md "v5.0 키 스킴 분열" 참조).
# 아래 표로 정규 12키 <-> alias 를 흡수해, 어느 스킴으로 쓰였든 같은 값을 낸다.
CANON12 = ('s01_opinion_thesis', 's02_thesis_catalysts', 's03_company_overview',
           's04_industry_competition', 's05_management_fieldcheck', 's06_financial',
           's07_valuation', 's08_esg', 's09_scenarios_risks',
           's10_earnings_consensus', 's11_supply_shareholder', 's12_action_plan')

_ALIAS = {'s01_opinion_thesis': 's01_opinion',
          's02_thesis_catalysts': 's02_investment_points',
          's04_industry_competition': 's04_industry',
          's06_financial': 's08_financial',
          's07_valuation': 's09_valuation',
          's09_scenarios_risks': 's10_scenarios_risks',
          's10_earnings_consensus': 's11_earnings_consensus'}

STORY_CANON = ('s02_thesis_catalysts', 's03_company_overview', 's04_industry_competition')

# 구 이름 (외부 참조 호환)
STORY_KEYS = ('s02_investment_points', 's03_company_overview', 's04_industry')
FINANCE_KEYS = ('s08_financial', 's09_valuation')

# --- 위닝펀드 수상작 12편 실측에서 나온 상수 ---
# 산업 26% / 기업 19% / 투자포인트 17% = 스토리 62%, 재무 12%, 밸류 16%
STORY_SHARE_MIN = 55      # 62% 에서 7%p 여유
HEADING_MAX = 1800        # 수상작 페이지당 1,000~1,500자 (한 페이지 = 한 주장)
ANCHOR_MIN_LEN = 200      # 이보다 짧은 블록은 산업->종목 착지 의무 면제
UNCOUNTED_MAX = 10        # 분모 밖 본문이 이 %를 넘으면 스키마 불명 -> 판정하지 않는다

# v5 에서 PDF 에 렌더되지 않는 부속 섹션 (verify_facts D6 용). 분모 밖이어도 정상.
_BENIGN_EXTRA = ('s13_thesis', 's14_short_thesis')

TABLE_MAX = {'s02_investment_points': 35, 's03_company_overview': 35,
             's04_industry': 35, 's08_financial': 45, 's09_valuation': 45}


def section_text(sections, canon):
    """정규 키가 **존재하면** 그 값이 최종이다. alias 는 정규 키가 없을 때만 본다.

    v5.9 병합 구조에서 호스트로 옮긴 섹션은 원본을 빈 문자열로 비운다.
    "비어 있으면 alias" 로 만들면 그 내용이 alias 를 통해 되살아나 분모에
    이중 계산된다 (와이지엔터 v7 실측: 스토리 56.9% 가 49.9% 로 잘못 나옴).
    """
    if canon in sections:
        return sections.get(canon) or ''
    a = _ALIAS.get(canon)
    return (sections.get(a) or '') if a else ''


def prose_len(text):
    """표 행을 뺀 산문 길이. 도표는 페이지에 같이 들어가므로 분량으로 세지 않는다."""
    return sum(len(ln) for ln in (text or '').splitlines()
               if not ln.strip().startswith('|'))


def table_ratio(text):
    """본문에서 마크다운 표 행이 차지하는 문자 비율(%).

    분자·분모 모두 **라인 길이 합**으로 센다. 분모에 len(text) 를 쓰면
    개행 문자가 분모에만 들어가 경계에서 몇 %p 씩 어긋난다.
    """
    if not text:
        return 0.0
    lines = text.splitlines()
    total = sum(len(ln) for ln in lines)
    if total == 0:
        return 0.0
    tbl = sum(len(ln) for ln in lines if ln.strip().startswith('|'))
    return tbl / total * 100


def check_c21_story_weight(sections):
    """C21: **본문 전체 대비** 스토리(투자포인트+기업+산업) 비중(%).

    반환: (비중%, 통과여부). 본문이 없으면 (None, None).

    구버전은 분모를 재무+밸류로 잡았는데 겨눈 곳이 틀렸다. 실측에서 재무 비중은
    수상작(12.3%)과 우리(11.9%)가 거의 같았고, 진짜 원인은 수상작에 존재하지도
    않는 섹션 5개(ESG·실행계획·수급·경영진·컨센)가 본문의 32% 를 먹은 것이었다.
    분모를 재무로 잡으면 그 32% 가 보이지 않는다.
    """
    counted = set()
    total = 0
    for k in CANON12:
        if k in sections:
            # 정규 키가 있으면 그 값이 최종 (빈 문자열 = 호스트로 병합 완료)
            counted.add(k)
            total += len(sections.get(k) or '')
            continue
        a = _ALIAS.get(k)
        if a and (sections.get(a) or '').strip():
            counted.add(a)
            total += len(sections[a])
    if total == 0:
        return None, None

    # 분모 밖에 본문이 크게 남아 있으면 다른 스키마다. **PASS 로 때우지 않는다.**
    # 실측(2026-09-08): 구 v4 리포트에 그대로 돌렸더니 삼성SDI 83.3% PASS,
    # 한화에어로 54.4% 가 나왔는데 둘 다 거짓값이었다. 삼성SDI 는 s05_competition
    # /s09_risk/s15_beat_miss 등 5,588자가 통째로 분모 밖이었다.
    # alias 키는 CLAUDE.md 가 재생성을 의무화한 사본이라 분모 밖이어도 정상이다.
    # (정규 키가 이미 세어졌으므로 여기서 또 세면 이중 계산이 된다.)
    uncounted = sum(len(v or '') for k, v in sections.items()
                    if k not in counted and k not in _BENIGN_EXTRA
                    and k not in set(_ALIAS.values()))
    if uncounted > total * UNCOUNTED_MAX / 100:
        return None, None

    story = sum(len(section_text(sections, k)) for k in STORY_CANON)
    share = story / total * 100
    return share, share >= STORY_SHARE_MIN


def split_heading_blocks(text):
    """`####` 소제목 단위로 (소제목, 본문) 분리. 소제목이 없으면 [('', 전체)]."""
    if not (text or '').strip():
        return []
    parts = re.split(r'^\s*#{3,4}\s*(.+?)\s*$', text, flags=re.M)
    if len(parts) == 1:
        return [('', text)]
    out = []
    if parts[0].strip():
        out.append(('', parts[0]))
    for k in range(1, len(parts) - 1, 2):
        out.append((parts[k].strip(), parts[k + 1]))
    return out


def check_c23_heading_blocks(sections):
    """C23: 스토리 3섹션의 소제목 블록이 HEADING_MAX 를 넘는지.

    수상작은 한 페이지 = 한 소제목 = 한 주장이다. 한 소제목 아래 1,800자가
    넘으면 주장이 뭉쳐 있다는 뜻이다. 반환: [(섹션, 소제목, 산문길이), ...]
    """
    over = []
    for k in STORY_CANON:
        t = section_text(sections, k)
        for title, body in split_heading_blocks(t):
            n = prose_len(body)
            if n > HEADING_MAX:
                over.append((k, title, n))
    return over



# --- C25 (v5.11): 문단마다 결론 한 줄 -------------------------------
# 실측: 위닝펀드 수상작 14편 중 **12편**이 본문 옆 여백에 그 문단의 결론을
# 한 줄로 단다("실질은 EPC 기업인", "①AI 투자→ ②PCB", "계속된 매출 성장과
# 수주잔고 -> 성장 사이클 유지"). 레이아웃 장식이 아니라 글쓰기 규율이다 --
# 한 문단의 결론을 한 줄로 못 쓰면 그 문단에는 논지가 없다.
MARGIN_PREFIX = '> **한 줄:**'
MARGIN_MAX = 40


def margin_note_of(block_body):
    """블록 본문에서 마진 노트 문구를 뽑는다. 없으면 None."""
    for ln in (block_body or '').splitlines():
        t = ln.strip()
        if t.startswith(MARGIN_PREFIX):
            return t[len(MARGIN_PREFIX):].strip()
    return None


def check_c25_margin_notes(sections):
    """스토리 3섹션의 각 소제목 블록에 결론 한 줄이 있는가.

    반환: [(섹션키, 소제목), ...]  -- 없거나 너무 긴 블록
    """
    bad = []
    for k in STORY_CANON:
        t = section_text(sections, k)
        if not (t or '').strip():
            continue
        for title, body in split_heading_blocks(t):
            if not title:
                continue
            note = margin_note_of(body)
            if note is None or len(note) > MARGIN_MAX:
                bad.append((k, title))
    return bad


def check_c24_industry_anchor(industry_text, stock_name):
    """C24: 산업분석의 각 소제목이 본 종목으로 착지하는가. 반환: 미착지 소제목 목록.

    수상작 실측(와이지엔터 p4 끝): "와이지엔터테인먼트도 이 세 흐름에서 벗어나
    있지 않으며, 4사 중 가장 낮은 PER 16배는 세 가지 외부 요인이 한꺼번에 누른
    결과다." 종목명이 한 번도 안 나오는 산업 소제목은 남의 산업 리포트다.
    """
    if not stock_name or not (industry_text or '').strip():
        return []
    stem = stock_name[:3]          # "와이지엔터" 와 "와이지엔터테인먼트" 를 함께 잡는다
    miss = []
    for title, body in split_heading_blocks(industry_text):
        if prose_len(body) < ANCHOR_MIN_LEN:
            continue
        if stem not in body and stem not in title:
            miss.append(title)
    return miss


def check_c22_table_overload(sections):
    """C22: 섹션별 표 비중 상한. 반환: [(섹션, 비중, 상한), ...]"""
    over = []
    for k, cap in TABLE_MAX.items():
        t = sections.get(k)
        if not t:
            continue
        r = table_ratio(t)
        if r > cap:
            over.append((k, round(r, 1), cap))
    return over


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

    # ----- C21. 스토리텔링 비중 -----
    _share, _ok = check_c21_story_weight(sections)
    if _share is None:
        print("  [- C21] 스토리 비중              판정 불가 -- "
              "정규 12키 밖 본문이 10% 초과(구 v4 스킴). "
              "재작성 시 v5 12키로 맞추면 판정된다")
    if _share is not None:
        total_checks += 1
        if not _ok:
            fail += 1
            print(f"  [✗ C21] 스토리 비중              {_share:.1f}% (55%+ 필요, 수상작 실측 62%) -- "
                  f"산업+기업+투자포인트가 본문에서 차지하는 몸집이 얇다")
        else:
            print(f"  [✓ C21] 스토리 비중              {_share:.1f}%")

    # ----- C23. 소제목 단위 주장 (한 페이지 = 한 주장) -----
    _fat = check_c23_heading_blocks(sections)
    total_checks += 1
    if _fat:
        fail += 1
        _d = ', '.join(f"{t or '(소제목없음)'} {n}자" for _k, t, n in _fat[:3])
        print(f"  [✗ C23] 소제목 블록 과대      {_d} -- 1,800자 초과. 주장을 쪼개라")
    else:
        print(f"  [✓ C23] 소제목 블록          전부 1,800자 이내")

    # ----- C24. 산업분석의 종목 착지 -----
    _sn = (d.get('meta') or {}).get('stock_name', '')
    _miss = check_c24_industry_anchor(section_text(sections, 's04_industry_competition'), _sn)

    # ----- C25. 문단 결론 한 줄 -----
    _nomargin = check_c25_margin_notes(sections)
    total_checks += 1
    if _nomargin:
        fail += 1
        _d = ', '.join(t for _k, t in _nomargin[:3])
        print(f"  [\u2717 C25] \ubb38\ub2e8 \uacb0\ub860 \ud55c \uc904        {_d} -- "
              f"'{MARGIN_PREFIX} ...' \ub204\ub77d/\uacfc\uc7a5 ({len(_nomargin)}\uac1c)")
    else:
        print(f"  [\u2713 C25] \ubb38\ub2e8 \uacb0\ub860 \ud55c \uc904        \uc804 \ube14\ub85d \ubcf4\uc720")
    if _sn:
        total_checks += 1
        if _miss:
            fail += 1
            print(f"  [✗ C24] 산업 종목 착지        {', '.join(_miss[:3])} -- "
                  f"종목명이 없는 산업 소제목은 남의 산업 리포트다")
        else:
            print(f"  [✓ C24] 산업 종목 착지        전 소제목 착지")

    # ----- C22. 표 과다 -----
    _over = check_c22_table_overload(sections)
    total_checks += 1
    if _over:
        fail += 1
        _d = ', '.join(f"{k} {r}%>{c}%" for k, r, c in _over)
        print(f"  [✗ C22] 표 과다                  {_d} -- 표를 줄이고 해석 산문을 붙일 것")
    else:
        print(f"  [✓ C22] 표 비중                  전 섹션 상한 이내")

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
