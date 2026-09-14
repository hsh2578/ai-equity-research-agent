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

# 고객사·경쟁사로 인정하는 고유명사. 업종 무관하게 자주 등장하는 전방/동종 기업.
# 이름을 다 열거할 수는 없으므로 **대문자 영문 2자 이상 + 알려진 한글 기업명**을
# 함께 센다. 정확도보다 '타사 고유명사를 쓰고 있는가'를 보는 지표다.
_KNOWN = (r'삼성전자|SK하이닉스|LG이노텍|LG디스플레이|현대차|기아|TSMC|ASML|Intel|인텔|'
          r'마이크론|Micron|Applied|Lam\s?Research|램리서치|도쿄일렉트론|KLA|NVIDIA|엔비디아|'
          r'미쓰이|신에츠|아사히|NGK|Canatu|카나투|imec|SEMI|WSTS|TrendForce|Gartner|IDC|'
          r'키옥시아|샌디스크|YMTC|CXMT|SMIC|NAURA|Micron')

CAPEX_PAT = (r'설비투자|시설투자|CAPEX|자본적\s*지출|컨퍼런스콜|컨콜|가이던스|'
             r'증설|램프업|양산\s*일정|팹\s*투자')
FILING_PAT = (r'공시(?:에|는|가|에서|했|한다|됐|된)|주요사항보고서|자기주식|주식소각|'
              r'교환사채|전환사채|유상증자|합병|실적변동|매출액\s*또는\s*손익구조|소속부')
PASTPAT = r'20[0-2]\d년[^.\n]{0,40}(?:감소|하락|적자|부진|줄었|감산|축소)'
EXT_PAT = (r'SEMI|WSTS|TrendForce|Gartner|IDC|옴디아|Omdia|카운터포인트|'
           r'ASML|시장조사|증권사\s*(?:정리|집계|분석)|업계\s*추산|외부\s*추정')


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
    quote = len(re.findall(r'"[^"\n]{12,}"|“[^”\n]{12,}”', text or ''))

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
