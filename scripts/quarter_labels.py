"""
분기 라벨 파싱 공용 모듈 (v5.5 신설)

배경 -- v4.20 에 신설한 B13(분기 누락 검증)이 실제로는 죽어 있었다.
analysis.json 의 quarterly 표는 **headers 에 분기 라벨**이 오고 rows 는 지표별 행이다:

    headers: ['항목', '1Q25', '2Q25', '3Q25', '4Q25', '1Q26']
    rows:    [['매출', ...], ['영업이익', ...]]

그런데 verify_numbers.py B13 은 rows[i][0] (= '매출', '영업이익')을 분기 라벨로 읽어
정규식이 한 건도 매칭되지 않았고, 에러 리스트가 비어 있으니 그대로 PASS 를 냈다.
한국콜마/와이지엔터 모두 "확정 4분기 충족" 이라는 잘못된 메시지로 통과했다.

이 모듈은 두 가지를 고친다:
  1. headers 와 rows **양쪽**에서 분기 라벨을 찾는다 (표 방향 무관).
     rows 는 list(첫 열이 라벨) / dict(키가 라벨) 두 형태 모두 처리한다 --
     v5.5 초판은 dict 를 순회하며 키 문자열만 얻고 조용히 버렸다.
  2. "최근 연도에 4분기가 다 있는가" 대신 **"연속된 분기 사이에 구멍이 있는가"** 를 본다.
     진행 중인 연도(예: 1Q26 까지만 발표)를 오탐하지 않으면서,
     에스엠 1Q25 누락 같은 실제 사고는 잡는다.
"""
import re

# 1Q25 / Q1'25 / Q1 25 / 1Q FY25 / 25.1Q / 1Q2025 를 모두 인식
# 주의: 연도 뒤에 \b 를 쓰면 "Q2'26E" 처럼 E/F 가 바로 붙는 추정 표기를 놓친다
# (E 가 단어문자라 경계가 성립하지 않음). (?!\d) 로 "숫자만 아니면 됨" 을 쓴다.
_PATTERNS = [
    re.compile(r'\b(\d)Q\s*(?:FY)?[\'’\s]*(\d{2,4})(?!\d)', re.I),   # 1Q25, 1Q FY25, 1Q2025, 1Q25E
    re.compile(r'\bQ(\d)\s*(?:FY)?[\'’\s]*(\d{2,4})(?!\d)', re.I),   # Q1'25, Q1 25, Q2'26E
    re.compile(r'\b(\d{2,4})\s*[.\-/]\s*(\d)Q\b', re.I),             # 25.1Q  (연도 선행)
    re.compile(r'\b(\d{4})\s+(\d)Q\b', re.I),                        # 2025 1Q (에스엠 실제 표기)
]

# _PATTERNS 중 그룹 순서가 (연도, 분기) 인 인덱스. 나머지는 (분기, 연도).
# 패턴을 추가할 때 이 집합 갱신을 빠뜨리면 연도를 분기로 읽어 조용히 None 이 된다.
_YEAR_FIRST = {2, 3}

# 연도 없는 맨 분기 (기아 실제 표기 '['', 'Q1', 'Q2', ...]') -- 연도를 특정할 수 없어
# 누락 판정이 불가능하다. 파싱 실패와 구분해서 별도 경고를 낸다.
_BARE_Q = re.compile(r'^\s*(?:Q\s*([1-4])|([1-4])\s*Q)\s*$', re.I)

# 추정/가이던스 표기 -- 확정 분기에서 제외
_EST_MARKERS = ('E)', '(E', 'E]', '추정', '가이던스', 'GUID', 'CONSENSUS', '컨센', 'F)', '(F')


def is_estimate(label: str) -> bool:
    up = str(label).upper().strip()
    if any(m in up for m in _EST_MARKERS):
        return True
    # 뒤에 붙은 단독 E/F (예: "2Q26E", "4Q25F", "Q2'26E")
    # 분기/연도 사이에 어포스트로피·점·하이픈이 낄 수 있다 (AMD 실제 표기 "Q2'26E").
    sep = r"['’.\-\s]*"
    return bool(
        re.search(rf'\dQ{sep}(?:FY)?{sep}\d{{2,4}}{sep}[EF]\b', up)
        or re.search(rf'Q\d{sep}(?:FY)?{sep}\d{{2,4}}{sep}[EF]\b', up)
    )


def parse_label(label: str):
    """'1Q25' -> (2025, 1). 인식 실패 시 None."""
    s = str(label).strip()
    if not s:
        return None
    for i, pat in enumerate(_PATTERNS):
        m = pat.search(s)
        if not m:
            continue
        if i in _YEAR_FIRST:            # 연도가 앞에 오는 패턴 (25.1Q / 2025 1Q)
            year_s, q_s = m.group(1), m.group(2)
        else:
            q_s, year_s = m.group(1), m.group(2)
        q = int(q_s)
        if not 1 <= q <= 4:
            return None
        y = int(year_s)
        if y < 100:
            y += 2000
        if not 1990 <= y <= 2100:
            return None
        return (y, q)
    return None


def _row_labels(rows):
    """rows 컨테이너에서 라벨 후보 문자열을 뽑는다.

    rows 는 실제 데이터에서 두 형태로 나온다 (analysis 39개 중 dict 14 / list 24):

      list 형: [['매출', 100, 110], ['영업이익', 10, 12]]   -> 첫 열이 라벨
      dict 형: {'매출액(억원)': [100, 110], '영업이익(억원)': [...]} -> **키가 라벨**

    과거에는 dict 를 그대로 `for row in rows` 로 돌려 키(문자열)만 얻었고,
    문자열은 list/tuple 분기에도 dict 분기에도 걸리지 않아 **조용히 무시**됐다.
    지금은 headers 가 항상 분기 라벨을 갖고 있어 가려져 있을 뿐, 전치(transpose)
    표(키가 '1Q25')가 오면 분기 누락이 통째로 미검증으로 통과한다.
    """
    out = []
    if isinstance(rows, dict):
        for key, val in rows.items():
            out.append(str(key))          # 전치 표: 키가 분기 라벨
            if isinstance(val, dict):     # {'1Q25': {'매출': ...}} 형태의 부가 라벨
                for k in ('period', 'quarter', 'label', '분기', '항목'):
                    if k in val:
                        out.append(str(val[k]))
                        break
        return out
    if not isinstance(rows, (list, tuple)):
        return out
    for row in rows:
        if isinstance(row, (list, tuple)) and row:
            out.append(str(row[0]))
        elif isinstance(row, dict):
            for key in ('period', 'quarter', 'label', '분기', '항목'):
                if key in row:
                    out.append(str(row[key]))
                    break
        elif isinstance(row, str):
            out.append(row)
    return out


def collect_quarters(quarterly: dict):
    """quarterly dict -> (confirmed, estimated, raw_labels)

    headers 와 rows 양쪽을 훑어 표 방향에 관계없이 라벨을 찾는다.
    rows 는 list(첫 열이 라벨) / dict(키가 라벨) 둘 다 처리한다.
    confirmed / estimated 는 (year, quarter) 튜플의 정렬된 리스트.
    """
    if not isinstance(quarterly, dict):
        return [], [], []

    candidates = []
    headers = quarterly.get('headers') or []
    if isinstance(headers, (list, tuple)):
        candidates.extend(str(h) for h in headers)

    candidates.extend(_row_labels(quarterly.get('rows')))

    confirmed, estimated, raw = [], [], []
    for c in candidates:
        parsed = parse_label(c)
        if not parsed:
            continue
        raw.append(c)
        (estimated if is_estimate(c) else confirmed).append(parsed)

    return sorted(set(confirmed)), sorted(set(estimated)), raw


def find_gaps(confirmed):
    """확정 분기 사이의 구멍을 찾는다. -> ['2Q25', '3Q25'] 형태의 누락 라벨 리스트.

    '최근 연도 4분기 충족' 대신 연속성을 본다. 진행 중 연도를 오탐하지 않는다.
    """
    if len(confirmed) < 2:
        return []
    idx = sorted((y * 4 + (q - 1)) for y, q in confirmed)
    missing = []
    for n in range(idx[0], idx[-1] + 1):
        if n not in idx:
            y, q = divmod(n, 4)
            missing.append(f"{q + 1}Q{str(y)[2:]}")
    return missing


def check(quarterly: dict, min_confirmed: int = 4):
    """B13 검증 본체. -> (errors: list[str], detail: str)"""
    confirmed, estimated, raw = collect_quarters(quarterly)
    errs = []

    if not quarterly or not (quarterly.get('rows') or quarterly.get('headers')):
        return ["quarterly 표 자체 부재 -- 분기 추세 없이 사이클 판단 불가"], "표 없음"

    if not confirmed and not estimated:
        headers = [str(x) for x in (quarterly.get('headers') or [])]
        bare = [h for h in headers if _BARE_Q.match(h)]
        if len(bare) >= 2:
            return ([f"분기 라벨에 연도가 없음: {bare[:6]} -- 어느 연도의 분기인지 특정 불가라 "
                     f"누락/YoY 검증이 불가능하다. '1Q25' 처럼 연도를 붙일 것 "
                     f"(quarterly.year 필드만으로는 표 자체가 자립하지 못함)"], "연도 없는 분기")
        return ([f"분기 라벨 파싱 실패 (headers/rows 어디에도 분기 표기 없음): "
                 f"{[h[:14] for h in headers[:5]]} "
                 f"-- '1Q25' 또는 \"Q1'25\" 형식 권장"], "파싱 실패")

    gaps = find_gaps(confirmed)
    if gaps:
        errs.append(f"확정 분기 사이 누락: {', '.join(gaps)} "
                    f"(일회성/사이클 판단이 왜곡된다. financial_summary.json quarterly 재확인)")

    if len(confirmed) < min_confirmed:
        errs.append(f"확정 분기 {len(confirmed)}개 (<{min_confirmed}) -- "
                    f"YoY/QoQ 비교와 일회성 판별에 최소 4개 필요")

    def _fmt(items):
        return ', '.join(f"{q}Q{str(y)[2:]}" for y, q in items) or '없음'

    detail = f"확정 {len(confirmed)}개 [{_fmt(confirmed)}] / 추정 {len(estimated)}개 [{_fmt(estimated)}]"
    return errs, detail
