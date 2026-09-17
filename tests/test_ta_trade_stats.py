"""ta_trade_stats 테스트. 관세청 XML 파싱과 TTM/YoY 계산만(네트워크 없음).

실행: python tests/test_ta_trade_stats.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_trade_stats as t  # noqa: E402

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


XML = '''<?xml version="1.0"?><response><header><resultCode>00</resultCode></header><body><items>
<item><expDlr>1744440255</expDlr><impDlr>174193205</impDlr><hsCd>-</hsCd><statCd>-</statCd><year>총계</year></item>
<item><expDlr>852533</expDlr><impDlr>3068</impDlr><hsCd>848610</hsCd><statCd>CN</statCd><year>2026.01</year></item>
<item><expDlr>900000</expDlr><impDlr>1000</impDlr><hsCd>848610</hsCd><statCd>CN</statCd><year>2026.02</year></item>
</items></body></response>'''
rows = t.parse_items(XML)
eq(len(rows), 2, '총계 행 제외')
eq(rows[0], {'ym': '202601', 'hs': '848610', 'country': 'CN', 'exp_usd': 852533, 'imp_usd': 3068}, '행 파싱')

series = [{'ym': f'{2024 + (i // 12)}{i % 12 + 1:02d}', 'exp_usd': 100 + i, 'imp_usd': 0} for i in range(24)]
y = t.ttm_yoy(series, '202512')
eq(y['exp_ttm'], sum(100 + i for i in range(12, 24)), '최근 12개월 합')
eq(y['exp_ttm_prev'], sum(100 + i for i in range(0, 12)), '직전 12개월 합')
eq(round(y['yoy'], 4), round(y['exp_ttm'] / y['exp_ttm_prev'] - 1, 4), 'yoy')
eq(t.ttm_yoy(series[:6], '202512'), None, '표본 부족이면 None')
imp = [{'ym': f'{2024 + (i // 12)}{i % 12 + 1:02d}', 'exp_usd': 0, 'imp_usd': 10 + i} for i in range(24)]
yi = t.ttm_yoy(imp, '202512')
eq((yi['yoy'], yi['imp_ttm'], round(yi['imp_yoy'], 4)), (None, sum(10 + i for i in range(12, 24)), round(sum(10 + i for i in range(12, 24)) / sum(10 + i for i in range(12)) - 1, 4)), '수입 종목: exp yoy None, imp yoy 계산')
eq(t.windows('202408', '202608'), [('202408', '202507'), ('202508', '202607'), ('202608', '202608')], '25개월 -> 12개월 창 3개')
eq(t.windows('202601', '202603'), [('202601', '202603')], '1년 이내면 창 하나')

print(f'ta_trade_stats 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for label, want, got in _failed:
    print(f'  [FAIL] {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
