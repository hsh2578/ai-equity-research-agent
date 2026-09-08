"""driver_scan.py -- 사업 구동 변수(driver)를 1차 출처에서 훑는다.

배경(2026-09 수상작 논증 정독): 수상작은 사업 사실에서 출발해 숫자로 간다.

    "G사 TPU v8x 'Zebrafish' 10월 양산 진입. 층수 24 -> 36층, M8급 CCL 채택으로
     기판당 ASP 상승"  (이수페타시스)

우리 투자포인트는 "컨센서스가 하반기에 상반기의 3.83배를 요구한다" 로 끝났다.
회계 논거만 있고 **회사가 무엇을 하는지**가 없었다.

실측해 보니 그런 사실이 **DART 안에 이미 있었다**. 못 쓴 이유는 데이터가 없어서가
아니라 grep 패턴이 재무 중심이라 안 잡은 것이다. 이 모듈이 P x Q - C 를 실제
변수명으로 훑는다.

evidence_scan 과 같은 원칙: **원문 문장 + line 번호**를 함께 준다.
위치가 붙으면 가짜 인용이 구조적으로 불가능하다.

사용: python scripts/driver_scan.py {종목명}
     -> data/{종목}/_drivers.md   (STEP 3 진입 전 Read 의무)
"""
import glob
import io
import os
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MIN_FILLED = 3          # 최소 이만큼은 숫자로 채워야 사업 논거를 쓸 수 있다
_MAX_LEN = 300

# P x Q - C 를 업종 무관 변수명으로 분해. 종목 유형별 세부는 v5.10 규칙 1 표 참조.
CATEGORIES = {
    '물량(Q)': [
        r'관객|모객|입장객|동원', r'초동|판매량|판매\s*장|출하|출고',
        r'가동률|생산\s*능력|생산능력|CAPA|캐파|증설',
        r'수주\s*(량|물량)', r'구독자|가입자|MAU|이용자',
        r'회차|공연\s*\d+\s*회|\d+\s*개\s*도시', r'점유율|M/S',
    ],
    '단가(P)': [
        r'객단가|ASP|평균\s*판매\s*가|판가|단가|티켓\s*(가격|단가)',
        r'스프레드|마진율|수수료율|NIM|ARPU',
    ],
    '비용(C)': [
        r'제작비|원가율|원재료|투입\s*단가|OEM\s*발주',
        r'감가상각|판관비율|마케팅\s*비|인건비|충당금',
    ],
    '고객·계약': [
        r'수주\s*잔고|수주잔고|수주\s*총액|신규\s*수주',
        r'주요\s*(고객|매출처)|납품|공급\s*계약|장기\s*계약|계약\s*기간',
    ],
    '일정': [
        r'양산|가동\s*개시|완공|준공|착공|개막|데뷔|출시|발매|인도',
    ],
}

_NUM = re.compile(r'\d')
# 사업 구동 변수가 아닌 문맥 (지배구조·감사·법무). 실측: 와이지엔터에서
# "외부감사인과의 계약 기간" 이 '계약 기간' 패턴에 걸려 드라이버로 잡혔다.
_OFFTOPIC = re.compile(
    r'감사인|감사위원|회계법인|정관|이사회|주주총회|등기|임원\s*(보수|현황)|'
    r'스톡옵션|주식매수선택권|소송|제재|공시위반|내부회계')
# 숫자처럼 보이지만 드라이버가 아닌 것 (연도·조항·페이지만 있는 문장)
_NOISE = re.compile(r'^\s*(제\s*\d+\s*(조|항|호)|목\s*차|페이지)')


def _sentences(text):
    """(line 번호, 문장). 줄 단위로 세고 줄 안에서 마침표로 쪼갠다."""
    out = []
    for ln, raw in enumerate(text.splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        for part in re.split(r'(?<=[.!?])\s+', raw):
            p = part.strip()
            if p:
                out.append((ln, p))
    return out


def scan_text(text):
    """드라이버 후보 문장 -> [{'category','text','line','matched'}]  (중복 제거)"""
    hits, seen = [], set()
    for ln, sent in _sentences(text or ''):
        if not _NUM.search(sent) or _NOISE.match(sent) or _OFFTOPIC.search(sent):
            continue
        for cat, pats in CATEGORIES.items():
            hit = None
            for p in pats:
                m = re.search(p, sent)
                if m:
                    hit = m.group(0)
                    break
            if not hit:
                continue
            # 말줄임표를 포함해 _MAX_LEN 을 넘지 않는다 (300 은 300 이어야 한다)
            body = sent if len(sent) <= _MAX_LEN else sent[:_MAX_LEN - 3].rstrip() + '...'
            key = (cat, body[:80])
            if key in seen:
                break
            seen.add(key)
            hits.append({'category': cat, 'text': body, 'line': ln, 'matched': hit})
            break          # 한 문장은 한 카테고리에만
    return hits


def scan_stock(stock_name, limit_per_cat=8):
    """data/{종목}/ 의 DART 전문·SEC 덤프를 훑어 _drivers.md 를 만든다."""
    d = os.path.join('data', stock_name)
    files = sorted(glob.glob(os.path.join(d, '_dart_FULL*.txt'))) + \
        sorted(glob.glob(os.path.join(d, '_sec_*.txt')))
    if not files:
        return None, ['1차 출처 전문이 없다 (_dart_FULL*.txt / _sec_*.txt)']

    by_cat = {c: [] for c in CATEGORIES}
    for path in files:
        with open(path, encoding='utf-8', errors='replace') as f:
            text = f.read()
        base = os.path.basename(path)
        for h in scan_text(text):
            if len(by_cat[h['category']]) < limit_per_cat:
                h['file'] = base
                by_cat[h['category']].append(h)

    filled = [c for c, v in by_cat.items() if v]
    lines = [f'# 사업 구동 변수 -- {stock_name}', '',
             '> `driver_scan.py` 가 1차 출처 전문에서 뽑은 **원문 문장 + 위치**다.',
             '> 재무제표는 결과이고 이것이 원인이다. 인용은 여기서만 한다.',
             f'> 채워진 카테고리 {len(filled)}/{len(CATEGORIES)} '
             f'(최소 {MIN_FILLED}개 필요 -- v5.10 규칙 1)', '']
    for cat in CATEGORIES:
        rows = by_cat[cat]
        lines.append(f'## {cat}')
        if not rows:
            lines.append('')
            lines.append('**미확인** -- 이 항목에 대한 수치 주장을 하지 않는다.')
            lines.append('')
            continue
        lines.append('')
        for h in rows:
            lines.append(f"- ({h['file']}:{h['line']}) `{h['matched']}` -- {h['text']}")
        lines.append('')

    warn = []
    if len(filled) < MIN_FILLED:
        warn.append(f'채워진 변수 {len(filled)}개 < {MIN_FILLED} -- '
                    f'회계 논거만으로 써야 하며 그 한계를 s01 에 명시할 것')
    out = os.path.join(d, '_drivers.md')
    tmp = out + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    os.replace(tmp, out)
    return out, warn


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    name = sys.argv[1]
    path, warns = scan_stock(name)
    if not path:
        for w in warns:
            print(f'[ERR] {w}')
        raise SystemExit(1)
    print(f'[OK] saved: {path}')
    for w in warns:
        print(f'[WARN] {w}')
