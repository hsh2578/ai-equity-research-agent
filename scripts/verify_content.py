# -*- coding: utf-8 -*-
"""verify_content.py -- 본문이 '회사 밖'을 다뤘는가 (v5.21 신설).

배경(2026-09 에프에스티): 초판은 DART 정기보고서와 FnGuide 만으로 썼고
사용자가 "재무로 도배됐다"고 했다. 결론을 바꾼 발견 다섯 개는 전부
정기보고서 **밖**에서 나왔다.

    자사주 처분목적 "EUV펠리클 확장 투자 재원"   <- DART 수시공시
    미쓰이가 CNT 연 5,000장 설비를 먼저 지음     <- 경쟁사 조사
    DRAM 은 EUV 펠리클을 쓰지 않는다             <- 전방 수요 조사
    카나투 로열티 구조                          <- 뉴스·해외 공시
    컨센 영업이익 88억 < 상반기 확정 110억        <- Wisereport

한국IR협의회 기업분석 16편을 정독해 보면 **산업현황 한 페이지가 통째로
고객사·경쟁사 이야기**다(아스플로 실측: 삼성·SK·마이크론·TSMC·인텔로 채우고
동사는 마지막 한 문장). 우리 초판은 거의 전부 회사 내부 숫자였다.

verify_tone 이 '어떻게 썼는가'를 본다면 이 파일은 **'무엇을 다뤘는가'**를 본다.
둘 다 없으면 체크리스트를 채운 회사 내부 요약문이 나온다.

사용: python scripts/verify_content.py {종목명}
"""
import io
import json
import os
import re
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 타사 고유명사를 세는 자리. **업종을 가리지 않아야 한다** -- 처음에는 반도체
# 기업명만 열거해 두었다가 CJ프레시웨이에서 삼성웰스토리·현대그린푸드·아워홈이
# 본문에 가득한데 0종으로 나왔다. 이름 목록으로는 업종을 따라갈 수 없다.
# 그래서 ① 회사명 접미사를 붙인 한글 고유명사 ② 알려진 대형사 세 갈래로 센다.
_CORP_SUFFIX = (r'전자|화학|푸드|홀딩스|리테일|물산|건설|중공업|제일제당|생명|화재|'
                r'에너지|머티리얼즈|테크|반도체|바이오|제약|통신|카드|증권|은행|백화점|'
                r'웰스토리|그린푸드|아워홈|프레시원|호텔|리조트|식품|유통|산업|공업|'
                r'디스플레이|이노텍|일렉트릭|하이닉스|모비스|엔지니어링')
_KNOWN = (r'[가-힣A-Za-z]{2,8}(?:' + _CORP_SUFFIX + r')|'
          r'삼성전자|현대차|기아|TSMC|ASML|Intel|인텔|마이크론|Micron|램리서치|'
          r'엔비디아|NVIDIA|미쓰이|신에츠|카나투|Canatu|키옥시아|SMIC|CXMT|'
          r'쿠팡|배민상회|네이버|카카오|롯데|신세계|이마트|한화|LIG홈앤밀|'
          r'푸디스트|마켓보로|식봄|도쿄일렉트론|KLA|삼성물산|동원')

# 전방 수요를 증명하는 말. 제조업의 CAPEX 뿐 아니라 수주·발주·입찰·재계약처럼
# 업종마다 다른 형태를 함께 센다 (식품·유통은 팹 투자라는 말을 쓰지 않는다).
CAPEX_PAT = (r'설비투자|시설투자|CAPEX|자본적\s*지출|컨퍼런스콜|컨콜|가이던스|'
             r'증설|램프업|양산\s*일정|팹\s*투자|신규\s*수주|수주(?:액|잔고|물량|를|가|한)|'
             r'발주|입찰|재계약|인수(?:했|하며|한|를|가)|출점|점포\s*확대|'
             r'투자\s*계획|단가\s*(?:인상|조정)|예산\s*(?:편성|증액)')
FILING_PAT = (r'공시(?:에|는|가|에서|했|한다|됐|된)|주요사항보고서|자기주식|주식소각|'
              r'교환사채|전환사채|유상증자|합병|실적변동|매출액\s*또는\s*손익구조|소속부')
PASTPAT = r'20[0-2]\d년[^.\n]{0,40}(?:감소|하락|적자|부진|줄었|감산|축소)'
# 외부 기관. 반도체 조사기관만 두면 다른 업종이 전부 0 이 된다.
EXT_PAT = (r'SEMI|WSTS|TrendForce|Gartner|IDC|옴디아|Omdia|카운터포인트|닐슨|Nielsen|'
           r'통계청|국가데이터처|한국은행|농림축산식품부|한국농수산식품유통공사|aT|'
           r'공정거래위원회|국토교통부|산업통상자원부|보건복지부|국방부|한국기업평가|'
           r'시장조사|증권사\s*(?:정리|집계|분석)|업계\s*(?:추산|집계|보도|진단)|외부\s*추정')


# v5.0 키 스킴 분열로 생긴 alias 키. 정규 키와 내용이 같으므로 세면 두 번 센다.
# K1~K6 은 밀도가 아니라 **절대 건수** 기준이라 중복이 그대로 통과로 이어진다.
ALIAS_KEYS = ('s01_opinion', 's02_investment_points', 's04_industry', 's08_financial',
              's09_valuation', 's10_scenarios_risks', 's11_earnings_consensus')


def body_keys(sections, meta=None):
    return ((meta or {}).get('section_order')
            or [k for k in sections if k not in ALIAS_KEYS])


def load(stock_name):
    p = os.path.join(ROOT, 'scripts', f'analysis_{stock_name}.json')
    if not os.path.exists(p):
        return None, None
    d = json.load(open(p, encoding='utf-8'))
    secs = d.get('sections') or {}
    order = body_keys(secs, d.get('meta'))
    return d, '\n'.join(secs.get(k) or '' for k in order)


def has_filings_file(stock_name):
    return os.path.exists(os.path.join(ROOT, 'data', stock_name, '_dart_filings.json'))


def check(text, stock_name=None):
    """반환: [(코드, 라벨, 상태, 실측, 기준, 왜)]"""
    chars = len(re.sub(r'\s', '', text or '')) or 1
    names = set(re.findall(_KNOWN, text or ''))
    n_names = len(names)
    capex = len(re.findall(CAPEX_PAT, text or ''))
    filing = len(re.findall(FILING_PAT, text or ''))
    past = len(re.findall(PASTPAT, text or ''))
    ext = len(re.findall(EXT_PAT, text or ''))
    # 인용은 줄바꿈을 넘어간다. 줄 단위로만 보면 두 줄짜리 인용이 통째로 빠진다
    # (CJ프레시웨이 실측: 인용 박스 5개인데 2건으로 셌다).
    quote = len(re.findall(r'"[^"]{12,}"|“[^”]{12,}”', text or '', flags=re.S))

    rows = [
        ('K1', '타사 고유명사(고객·경쟁)', n_names >= 5, f'{n_names}종',
         '>= 5종',
         '산업현황이 동사 이야기만이면 남의 산업 리포트가 아니라 회사 요약문이다'),
        ('K2', '전방 투자·가이던스', capex >= 8, f'{capex}회', '>= 8회',
         '고객사 CAPEX 와 컨퍼런스콜 발언이 없으면 수요 논거가 서술로만 남는다'),
        ('K3', '공시 인용', filing >= 6, f'{filing}회', '>= 6회',
         '수시공시는 회사가 "왜 했는가"를 직접 말하는 유일한 문서다'),
        ('K4', '과거 실측 사례', past >= 2, f'{past}건', '>= 2건',
         '리스크는 확률표보다 같은 일이 벌어졌던 해의 숫자가 설득력 있다'),
        ('K5', '외부 기관·조사 인용', ext >= 3, f'{ext}회', '>= 3회',
         '시장 규모와 전방 전망을 자체 추정으로만 쓰면 근거가 닫힌다'),
        ('K6', '원문 인용 문장', quote >= 3, f'{quote}건', '>= 3건',
         '공시·컨콜 원문을 그대로 인용한 대목이 있어야 재현 가능하다'),
    ]
    # 종목명이 없으면 수집 여부를 알 수 없다. 모르는 것을 '수집됨'으로 적으면
    # 안 돌린 종목이 통과한다 -- 행 자체를 내지 않는다(호출부 main 은 항상 넘긴다).
    if stock_name:
        ok = has_filings_file(stock_name)
        rows.append(('K7', '수시공시 수집 여부', ok, '수집됨' if ok else '없음', '필요',
                     'collect_dart_filings.py 를 돌리지 않았다 -- K3 의 재료가 없다'))
    return rows


def main(stock_name):
    d, text = load(stock_name)
    if d is None:
        print(f'[ERR] scripts/analysis_{stock_name}.json 없음')
        return 2
    print('=' * 74)
    print(f'  verify_content (v5.21): {stock_name}')
    print('  본문이 회사 밖(고객·경쟁·공시·외부조사)을 다뤘는가')
    print('=' * 74)
    fail = 0
    for code, label, ok, got, want, why in check(text, stock_name):
        icon = '✓' if ok else '✗'
        print(f'  [{icon} {code}] {label:22s} {got:>8s}  (기준 {want})')
        if not ok:
            fail += 1
            if why:
                print(f'           -> {why}')
    print(f'\n  본문 {len(re.sub(chr(92) + "s", "", text)):,}자 / FAIL {fail}건')
    if fail:
        print('  [차단] 회사 내부 숫자만으로 쓰였다. 고객사 투자 계획, 경쟁사 실명과')
        print('         스펙, 수시공시 원문을 본문에 넣은 뒤 다시 돌린다.')
    else:
        print('  [OK] 회사 밖 커버리지 통과.')
    print('=' * 74)
    return 1 if fail else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('사용: python scripts/verify_content.py {종목명}')
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
