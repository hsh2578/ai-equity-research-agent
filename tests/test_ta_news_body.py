"""ta_news_body 테스트: 본문 추출 순수 함수(네트워크 없음).

실행: python tests/test_ta_news_body.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_news_body as nb  # noqa: E402

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


NAVER = '<html><body><div id="dic_area">첫 문장입니다. <br> 둘째 문장입니다.<span class="end_photo_org">사진</span></div></body></html>'
eq(nb.extract_body(NAVER, 'https://n.news.naver.com/mnews/article/215/0001'), '첫 문장입니다. 둘째 문장입니다. 사진', '네이버 #dic_area')
eq(nb.extract_body('<html><body><p>x</p></body></html>', 'https://n.news.naver.com/mnews/article/1/1'), '', '네이버 본문 없으면 빈 문자열')
eq(nb.needs_fetch({'body': 'a' * 100}), True, '요약 150자 미만이면 수집')
eq(nb.needs_fetch({'body': 'a' * 100, 'body_full': 'b' * 500}), False, '이미 본문 있으면 건너뜀')
eq(nb.needs_fetch({'body': 'a' * 800}), False, '본문이 길면 이미 전문')

print(f'ta_news_body 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for label, want, got in _failed:
    print(f'  [FAIL] {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
