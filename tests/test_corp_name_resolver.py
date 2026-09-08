"""corp_name_resolver -- 통용명과 등록명/증권가 표기의 차이를 흡수하는가.

실측 사고(2026-09-08 LS일렉트릭):
  1) DART 등록명이 '엘에스일렉트릭' 이라 get_corp_code('LS일렉트릭') 이 ValueError.
     dart_api 만 죽은 게 아니라 dart_quarterly 까지 같은 줄에서 죽어 분기 실측이 비었다.
  2) 한경 리포트 제목은 전부 'LS ELECTRIC(010120)' 이라 증권사 리포트 매칭 0건.
     2,161건을 훑고도 정독 의무(v5.10 규칙 2)가 통째로 건너뛰어졌다.
둘은 같은 뿌리다 -- **이름 표기 한 줄이 파이프라인을 조용히 끊는다.**
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from corp_name_resolver import resolve, variants, is_stock_code   # noqa: E402

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


ROWS = [
    ('엘에스일렉트릭', '00105855', '010120'),
    ('LS', '00110875', '006260'),
    ('LS머트리얼즈', '01234567', '417200'),
    ('LS에코에너지', '01111111', '229640'),
    ('에스케이하이닉스', '00164779', '000660'),
    ('삼성전자', '00126380', '005930'),
    ('포스코홀딩스', '00155319', '005490'),
    ('비상장회사', '00999999', ''),
]

# --- 종목코드는 이름 문제를 아예 우회한다 ---
eq(is_stock_code('010120'), True, "6자리 숫자는 종목코드")
eq(is_stock_code('0101201'), False, "7자리는 종목코드가 아니다")
eq(is_stock_code('LS'), False, "문자는 종목코드가 아니다")
eq(resolve(ROWS, '010120')[0], '엘에스일렉트릭', "종목코드로 직행 조회")
eq(resolve(ROWS, '999999'), None, "없는 코드는 None")

# --- 로마자 <-> 한글 음차 ---
eq(resolve(ROWS, 'LS일렉트릭')[0], '엘에스일렉트릭', "통용명 -> DART 등록명")
eq(resolve(ROWS, '엘에스일렉트릭')[0], '엘에스일렉트릭', "등록명 그대로도 찾는다")
eq(resolve(ROWS, 'SK하이닉스')[0], '에스케이하이닉스', "SK -> 에스케이")
eq(resolve(ROWS, 'POSCO홀딩스')[0], '포스코홀딩스', "POSCO -> 포스코")

# --- 증권가 영문 표기 ---
eq(resolve(ROWS, 'LS ELECTRIC')[0], '엘에스일렉트릭', "증권가 영문 표기도 같은 회사")
eq('LS ELECTRIC' in variants('LS일렉트릭'), True, "'LS ELECTRIC' 변형을 만든다")
eq('엘에스일렉트릭' in variants('LS일렉트릭'), True, "한글 음차 변형도 만든다")

# --- 오탐 방지: 비슷한 이름을 잘못 끌어오면 더 나쁘다 ---
eq(resolve(ROWS, 'LS')[0], 'LS', "완전일치가 부분일치를 이긴다")
eq(resolve(ROWS, 'LS머트리얼즈')[0], 'LS머트리얼즈', "같은 접두어의 다른 회사")
eq(resolve(ROWS, 'LS에코에너지')[0], 'LS에코에너지', "접미어가 겹쳐도 정확히")
eq(resolve(ROWS, '삼성전자')[0], '삼성전자', "한글 사명은 그대로")
eq(resolve(ROWS, '없는회사이름'), None, "없으면 None -- 아무거나 주지 않는다")
eq(resolve(ROWS, '비상장회사'), None, "상장사만 대상")
eq(resolve(ROWS, ''), None, "빈 문자열은 None")
eq(resolve(ROWS, None), None, "None 입력도 안전")

# --- variants 계약 ---
eq(variants('LS일렉트릭')[0], 'LS일렉트릭', "입력 그대로가 1순위")
eq(len(variants('LS일렉트릭')) == len(set(variants('LS일렉트릭'))), True, "중복 없음")
eq(variants(''), [], "빈 입력은 빈 목록")

print('=' * 62)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  corp_name_resolver 종목명 해석: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 62)
sys.exit(1 if _failed else 0)
