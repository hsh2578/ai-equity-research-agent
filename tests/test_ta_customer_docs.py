"""ta_customer_docs 테스트: 키워드 문단 추출만(네트워크 없음).

실행: python tests/test_ta_customer_docs.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_customer_docs as c  # noqa: E402

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


TEXT = ("line one\nWe expect capital expenditures of $4.0 billion in fiscal 2026.\nunrelated\n" + "x" * 50 +
        "\nOur Korea revenue grew 20% driven by memory customers.\nboilerplate forward-looking statements safe harbor\n")
hits = c.pick_paragraphs(TEXT, ['capex', 'capital expenditure', 'korea'], window=80, max_n=5)
eq([h['line'] for h in hits], [2, 5], '키워드 줄 번호(1-base), 중복 없이')
eq(hits[0]['quote'].startswith('We expect capital'), True, '인용은 원문 그대로')
eq(c.pick_paragraphs(TEXT, ['nothing']), [], '없으면 빈 리스트')
eq(len(c.pick_paragraphs("capex\n" * 100, ['capex'], max_n=3)), 3, 'max_n 상한')
eq(c.is_boilerplate('forward-looking statements safe harbor'), True, '보일러플레이트 제외')
eq(c.is_boilerplate('capex rose'), False, '일반 문장은 통과')

print(f'ta_customer_docs 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for label, want, got in _failed:
    print(f'  [FAIL] {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
