"""corp_name_resolver.py -- DART 등록명과 통용명의 차이를 흡수한다.

사고(2026-09-08, LS일렉트릭): DART 등록명이 **엘에스일렉트릭** 이라
`get_corp_code('LS일렉트릭')` 이 ValueError 로 죽었다. 그게 dart_api 하나로
끝나지 않고 `dart_quarterly.py` 까지 같은 지점에서 죽어 분기 실측이 통째로
비었다. 즉 **이름 한 줄이 파이프라인 전체를 조용히 끊는다.**

DART 는 로마자 사명을 한글 음차로 등록한 회사가 많다(엘에스·에스케이·
지에스·씨제이...). 반대로 로마자 그대로인 회사도 있다(LS, LS머트리얼즈).
그래서 한쪽으로 통일할 수 없고 **양방향으로 시도**해야 한다.

해결 3단 (앞에서 맞으면 멈춘다):
  1. 6자리 숫자면 종목코드로 직접 찾는다 -- 이름 문제를 아예 우회한다
  2. 입력 그대로 (완전일치 -> 부분일치)
  3. 로마자<->한글 음차 치환본으로 재시도

`--check` 로 회귀 확인: python scripts/corp_name_resolver.py --check
"""
import io
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# DART 등록명에서 실제로 관찰되는 음차. 한 글자짜리(H, K)는 오탐이 커서 뺀다.
ROMAN_TO_HANGUL = {
    'LS': '엘에스', 'SK': '에스케이', 'GS': '지에스', 'CJ': '씨제이',
    'KT': '케이티', 'LG': '엘지', 'DL': '디엘', 'HD': '에이치디',
    'BGF': '비지에프', 'NH': '엔에이치', 'DB': '디비', 'JB': '제이비',
    'BNK': '비엔케이', 'HL': '에이치엘', 'POSCO': '포스코',
    'HMM': '에이치엠엠', 'SNT': '에스엔티', 'TCC': '티씨씨',
    'KCC': '케이씨씨', 'OCI': '오씨아이', 'AJ': '에이제이',
    'KG': '케이지', 'SGC': '에스지씨', 'STX': '에스티엑스',
}
HANGUL_TO_ROMAN = {v: k for k, v in ROMAN_TO_HANGUL.items()}

# 사명 뒤쪽의 외래어 접미어. 증권가 리포트 제목은 'LS ELECTRIC' 처럼 영문으로,
# DART 는 '엘에스일렉트릭' 처럼 한글로 적는 일이 흔하다. 둘 다 만들어 둔다.
SUFFIX_KO_EN = {
    '일렉트릭': 'ELECTRIC', '홀딩스': 'HOLDINGS', '에너지': 'ENERGY',
    '머트리얼즈': 'MATERIALS', '머티리얼즈': 'MATERIALS', '케미칼': 'CHEMICAL',
    '네트웍스': 'NETWORKS', '에코에너지': 'ECO ENERGY', '마린솔루션': 'MARINE SOLUTION',
    '이노텍': 'INNOTEK', '디스플레이': 'DISPLAY', '텔레콤': 'TELECOM',
}
SUFFIX_EN_KO = {v: k for k, v in SUFFIX_KO_EN.items()}


_CODE = re.compile(r'^\d{6}$')


def is_stock_code(s):
    """6자리 숫자면 종목코드로 본다."""
    return bool(_CODE.match((s or '').strip()))


def variants(name):
    """조회에 써 볼 이름 후보를 **우선순위 순서**로. 중복 없음."""
    name = (name or '').strip()
    if not name:
        return []          # 빈 후보를 흘리면 뒤에서 '아무거나 매칭' 이 된다
    out = [name]

    def add(v):
        v = v.strip()
        if v and v not in out:
            out.append(v)

    # 로마자 -> 한글 음차 (긴 키부터: POSCO 가 있으면 그것을 먼저)
    for r, h in sorted(ROMAN_TO_HANGUL.items(), key=lambda kv: -len(kv[0])):
        if name.upper().startswith(r):
            add(h + name[len(r):])
    # 한글 음차 -> 로마자
    for h, r in sorted(HANGUL_TO_ROMAN.items(), key=lambda kv: -len(kv[0])):
        if name.startswith(h):
            add(r + name[len(h):])
    # 외래어 접미어를 영문/한글 양쪽으로. 'LS일렉트릭' -> 'LS ELECTRIC'
    # (한경 리포트 제목이 전부 영문 표기라 이게 없으면 정독 의무가 통째로 건너뛰어진다)
    for base in list(out):
        for ko, en in SUFFIX_KO_EN.items():
            if base.endswith(ko):
                head = base[:-len(ko)]
                add(head + en)
                add(head + ' ' + en)
        up = base.upper()
        for en, ko in SUFFIX_EN_KO.items():
            for sep in (' ', ''):
                tail = sep + en
                if up.endswith(tail):
                    add(base[:len(base) - len(tail)] + ko)

    # 공백/하이픈 유무
    for base in list(out):
        if ' ' in base:
            add(base.replace(' ', ''))
    return out


def resolve(rows, query):
    """rows=[(corp_name, corp_code, stock_code)] 에서 (name, corp, stock) 또는 None.

    rows 는 호출자가 넘긴다 -- 이 모듈은 네트워크를 모른다(테스트 가능).
    """
    q = (query or '').strip()
    if not q:
        return None
    listed = [r for r in rows if (r[2] or '').strip()]

    # 1. 종목코드 직행
    if is_stock_code(q):
        for n, c, s in listed:
            if s.strip() == q:
                return (n, c, s.strip())
        return None

    # 2~3. 이름 후보를 순서대로, 각 후보마다 완전일치 -> 부분일치
    for cand in variants(q):
        for n, c, s in listed:
            if n == cand:
                return (n, c, s.strip())
    for cand in variants(q):
        hits = [(n, c, s.strip()) for n, c, s in listed if cand in n]
        if hits:
            # 짧은 이름이 대개 본체다 (엘에스일렉트릭 vs 엘에스일렉트릭판매)
            return min(hits, key=lambda r: len(r[0]))
    return None


def _check():
    rows = [
        ('엘에스일렉트릭', '00105855', '010120'),
        ('LS', '00110875', '006260'),
        ('LS머트리얼즈', '01234567', '417200'),
        ('에스케이하이닉스', '00164779', '000660'),
        ('삼성전자', '00126380', '005930'),
        ('포스코홀딩스', '00155319', '005490'),
        ('비상장회사', '00999999', ''),
    ]
    cases = [
        ('LS일렉트릭', '엘에스일렉트릭'),
        ('LS ELECTRIC', '엘에스일렉트릭'),      # 증권가 표기
        ('LS ELECTRIC(010120)', None),          # 코드 괄호는 별도 처리 대상이 아니다
        ('엘에스일렉트릭', '엘에스일렉트릭'),
        ('010120', '엘에스일렉트릭'),
        ('LS', 'LS'),                       # 완전일치가 부분일치를 이긴다
        ('LS머트리얼즈', 'LS머트리얼즈'),
        ('SK하이닉스', '에스케이하이닉스'),
        ('삼성전자', '삼성전자'),
        ('005930', '삼성전자'),
        ('POSCO홀딩스', '포스코홀딩스'),
        ('없는회사이름', None),
        ('비상장회사', None),               # 상장사만
        ('999999', None),
    ]
    bad = 0
    for q, want in cases:
        got = resolve(rows, q)
        name = got[0] if got else None
        ok = name == want
        bad += (not ok)
        print(f'  {"OK " if ok else "FAIL"}  {q!r:20} -> {name!r}'
              + ('' if ok else f'  (기대 {want!r})'))
    print(f'\n  {len(cases) - bad}/{len(cases)} 통과')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(_check() if '--check' in sys.argv else _check())
