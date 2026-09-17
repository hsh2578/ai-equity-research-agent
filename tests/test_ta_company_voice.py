"""ta_company_voice 테스트: 인터뷰·발언 기사 판별과 발언 문장 추출(네트워크 없음).

실행: python tests/test_ta_company_voice.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_company_voice as v  # noqa: E402

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


eq(v.is_company_statement('[인터뷰] 에프에스티 대표 "내년 EUV 양산"', ''), True, '제목 인터뷰')
eq(v.is_company_statement('에프에스티, 카나투 장비 증설', '회사 관계자는 "3분기 양산"이라고 밝혔다.'), True, '본문 발언')
eq(v.is_company_statement('[특징주] 에프에스티 급등', '주가가 12% 올랐다.'), False, '반응 기사 제외')
eq(v.is_company_statement('에프에스티 목표주가 상향', '증권사는 매수 의견을 유지했다.'), False, '증권사 의견 제외')
body = '앞 문장. 장경빈 대표는 "인증은 연내 마무리"라고 말했다. 회사 측은 반응기 추가 발주를 밝혔다. 끝.'
eq(v.extract_statements(body),
   ['장경빈 대표는 "인증은 연내 마무리"라고 말했다.', '회사 측은 반응기 추가 발주를 밝혔다.'], '발언 문장만')
eq(v.extract_statements('아무 발언 없음.'), [], '없으면 빈 리스트')
eq(v.extract_statements('한병도 원내대표는 소통의 장이 될 것이라고 강조했다.'), [], '정치인 발언 제외')

print(f'ta_company_voice 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for label, want, got in _failed:
    print(f'  [FAIL] {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
