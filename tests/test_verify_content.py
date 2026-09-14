"""verify_content -- '회사 밖'을 다뤘는가 (v5.21).

배경: 에프에스티 초판이 "재무로 도배됐다"고 읽힌 이유는 본문이 거의 전부
회사 **안** 숫자였기 때문이다. 결론을 바꾼 발견 다섯 개는 전부 정기보고서
밖(수시공시·경쟁사 조사·전방 수요·뉴스·컨센)에서 나왔다.

verify_tone 이 '어떻게 썼는가'를 본다면 이 검증기는 '무엇을 다뤘는가'를 본다.
여기서 지키는 것:
  1) K1~K6 은 **절대 건수** 기준이라 alias 섹션을 같이 세면 그대로 통과가 된다
  2) 키워드가 실제로 그 뜻으로 쓰였을 때만 센다 (부분일치 오검출 차단)
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from verify_content import body_keys, check   # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def status(text, code):
    for c, _lab, ok, *_ in check(text):
        if c == code:
            return ok
    return None


def got(text, code):
    for c, _lab, _ok, g, *_ in check(text):
        if c == code:
            return g
    return None


# ---------- K1 타사 고유명사 ----------
NAMES = ('삼성전자와 SK하이닉스가 주 고객이고 TSMC, 인텔, 마이크론도 검토 중이다. '
         '경쟁사는 미쓰이화학과 신에츠다.')
eq(status(NAMES, 'K1'), True, '고객·경쟁사 이름이 7종이면 통과')
eq(got(NAMES * 4, 'K1'), '7종',
   '**같은 이름을 네 번 써도 7종이다 -- 종류를 세야 한 회사 반복이 커버리지로 안 뒤바뀐다**')
eq(status('동사는 펠리클과 장비를 만든다. 매출은 늘었다.', 'K1'), False,
   '**회사 내부 이야기만이면 FAIL -- 산업분석이 아니라 회사 요약문이다**')

# ---------- K2 전방 투자·가이던스 ----------
capex = '설비투자 ' * 4 + '컨퍼런스콜 가이던스 증설 시설투자 '
eq(status(capex, 'K2'), True, '고객 CAPEX·컨콜 언급이 8회면 통과')
eq(status('설비투자를 늘린다.', 'K2'), False, '한 번 언급으로는 수요 논거가 서지 않는다')

# ---------- K3 공시 인용 ----------
FIL = ('자기주식 처분 공시에서 목적을 밝혔다. 주요사항보고서를 보면 교환사채다. '
       '유상증자 공시가 있었고 합병 공시도 났다. 매출액 또는 손익구조 변동 공시다.')
eq(status(FIL, 'K3'), True, '수시공시 인용 6회면 통과')
eq(status('공시자료실에서 확인할 수 있다.', 'K3'), False,
   '**"공시자료"처럼 뒤에 조사가 안 붙은 말은 인용이 아니다**')

# ---------- K4 과거 실측 사례 ----------
eq(status('2019년 메모리 다운턴에 매출이 32% 감소했다. '
          '2023년에도 반도체 투자가 축소됐다.', 'K4'), True,
   '과거 같은 일이 벌어진 해를 숫자로 들면 통과')
eq(status('업황이 나빠지면 매출이 감소할 수 있다.', 'K4'), False,
   '**연도 없는 일반론은 리스크 근거가 아니다**')
eq(status('2019년 이야기다.\n매출이 감소했다.\n2020년도 그렇다.\n적자였다.', 'K4'), False,
   '**줄이 바뀌면 같은 문장이 아니다 -- 멀리 떨어진 두 단어를 엮지 않는다**')

# ---------- K5 외부 기관 ----------
eq(status('SEMI 집계와 TrendForce 전망, 옴디아 조사를 인용한다.', 'K5'), True,
   '외부 조사기관 3곳이면 통과')
eq(status('자체 추정으로는 시장이 커진다.', 'K5'), False,
   '자체 추정만 쓰면 근거가 닫힌다')

# ---------- K6 원문 인용 ----------
eq(status('"EUV 펠리클 확장 투자 재원 확보" "연 5,000장 설비를 선행 구축" '
          '"DRAM 에는 적용하지 않는다"', 'K6'), True,
   '12자 이상 인용 3건이면 통과')
eq(status('"짧은 말" "또 짧다" "역시 짧다"', 'K6'), False,
   '**너무 짧은 따옴표는 인용이 아니라 강조다**')

# ---------- alias 섹션 이중 계산 차단 ----------
secs = {'s04_industry_competition': NAMES, 's04_industry': NAMES,
        's06_financial': capex, 's08_financial': capex}
eq(body_keys(secs), ['s04_industry_competition', 's06_financial'],
   '**alias 키는 세지 않는다 -- K1~K6 은 절대 건수라 중복이 그대로 통과가 된다**')
eq(body_keys(secs, {'section_order': ['s06_financial']}), ['s06_financial'],
   'meta.section_order 가 있으면 그것을 따른다')

# ---------- 입력 방어 ----------
eq(len(check('')), 6, '빈 본문에서도 0 나누기 없이 6행이 나온다')
eq(status('', 'K1'), False, '빈 본문은 전부 FAIL 이 맞다')

print('=' * 66)
if _failed:
    for label, want, g in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {g!r}')
print(f'  verify_content 커버리지 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
