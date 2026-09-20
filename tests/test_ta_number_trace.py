# -*- coding: utf-8 -*-
"""ta_number_trace -- 숫자 역추적 테스트 (임시 폴더, 네트워크 없음).

실행: python tests/test_ta_number_trace.py
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_number_trace as nt  # noqa: E402

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


secs = {'s01_opinion_thesis': '2026년 9월 30일 8월 통계. 영업이익 1,671억원(+121.8%), 13개 점포, 배당 450억원, PER 7.55배',
        's06_financial': '순차입금 3조2,565억원, 2023년 매출 63,571'}
nums = nt.body_numbers(secs)
toks = [t for _, t, _, _ in nums]
eq('2026' in toks, False, '연도는 뺀다')
eq('30' in toks or '13' in toks, False, '날짜·개수 서수는 뺀다')
eq('1,671' in toks and '121.8' in toks and '7.55' in toks, True, '금액·비율·배수는 센다')

with tempfile.TemporaryDirectory() as d:
    files = [os.path.join(d, 'a.txt'), os.path.join(d, 'b.json')]
    open(files[0], 'w', encoding='utf-8').write('영업이익 1,671억(YoY 121.8%) 배당금수익 24,255백만 순차입 32,565 이평 443970.25')
    json.dump({'per_12m_forward': 7.55, 'rev_2023': 63571}, open(files[1], 'w', encoding='utf-8'))
    have = nt.corpus_numbers([(files[0], nt.FIN), (files[1], nt.EXT)])
    eq(have['1671'], {nt.FIN}, '재무 파일의 숫자는 재무공시 카테고리')
    eq(have['7.55'], {nt.EXT}, 'json 을 외부로 넘기면 외부 카테고리')
    ta = os.path.join(d, 'ta')
    eq(nt._category(os.path.join(d, 'financial_summary.json'), ta), nt.FIN, 'data/{종목}/ 직하는 재무공시')
    eq(nt._category(os.path.join(ta, 'reports', 'company', 'nv_1.txt'), ta), nt.EXT, '리포트 원문은 외부')
    eq(nt._category(os.path.join(ta, 'assumptions.json'), ta), nt.LEDGER, 'assumptions 는 장부')
    eq(nt._category(os.path.join(ta, 'synthesis.md'), ta), None, '논쟁 메모는 근거가 아니다')
    eq('1671' in have and '121.8' in have and '7.55' in have and '63571' in have, True, '코퍼스 숫자 정규화(콤마 제거)')
    eq('450' in have, False, '450억은 코퍼스에 없다')
    eq('443970' in have, True, '소수 코퍼스 값은 반올림 정수로도 들어간다')
    # trace 로직만 재현 (파일 경로 의존 없이)
    missing = [(s, t) for s, t, _, a in nums if nt._norm(t) not in have and not (a and a in have)]
    eq(('s01_opinion_thesis', '450') in missing, True, '근거 없는 450억을 잡는다')
    eq(any(t == '45' for _, t, _, _ in nums), False, '두 자리 이하는 세지 않는다(설계)')
    eq(any(a == '32565' for _, t, _, a in nums if t == '2,565'), True, '3조2,565억 -> 32565 결합값')
    eq(any(t == '2,565' for _, t in missing), False, '결합값 32565 가 코퍼스에 있으면 통과')
    eq(any(t == '63,571' for _, t in missing), False, 'json 의 63571 로 63,571 이 통과한다')

print('=' * 66)
for label, want, got in _failed:
    print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_number_trace 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
