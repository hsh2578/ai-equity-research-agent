"""
wf_chart_planner 표 파싱 테스트 (financials/quarterly 자료형 3종)

실행: python tests/test_wf_chart_planner.py

배경 -- /wf-report 1단계가 종목 절반에서 죽어 있었다.
`_fin_row` 가 `financials.rows` 를 dict 로만 가정하고 `.items()` 를 호출하는데,
실제 analysis 파일의 약 절반(AMD/TSLA/MSFT/기아/삼성전자/현대차/template ...)은
rows 가 list of lists 다. `b_dupont_roe` 가 SECTION_DEFAULTS 에 있어 무조건 실행되므로
그 종목들은 `python scripts/wf_chart_planner.py AMD ...` 첫 줄에서
AttributeError: 'list' object has no attribute 'items' 로 중단됐다.

실제 파일에 존재하는 표 형태는 3가지다:
  A) rows dict            : {지표: [값...]},         기간 = headers[1:]   (에스엠/JYP/두산 ...)
  B) rows list, 지표행     : [[지표, 값...]],          기간 = headers[1:]   (AMD/기아/카카오 ...)
  C) rows list, 전치       : [[기간, 값...]],          지표 = headers[1:]   (GS리테일/삼성전자 quarterly ...)
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import wf_chart_planner as P

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


def no_raise(fn, name):
    global _passed
    try:
        fn()
        _passed += 1
    except Exception as exc:
        _failed.append(f"{name}\n      예외: {type(exc).__name__}: {exc}")


# --- 실제 파일에서 뜬 표 샘플 ---
FIN_DICT = {  # 에스엠 실제 형태 (A)
    'headers': ['항목', '2022', '2023', '2024', '2025', '2026E'],
    'rows': {
        '매출액(억원)': [8508, 9611, 9897, 11749, 12862],
        '영업이익(억원)': [910, 1135, 873, 1830, 2012],
        'ROE(%)': [8.1, 9.4, 6.2, 12.0, 12.8],
    },
}

FIN_LIST = {  # AMD 실제 형태 (B)
    'headers': ['항목', 'FY22', 'FY23', 'FY24', 'FY25', 'FY26E'],
    'rows': [
        ['매출 (억 달러)', '236', '227', '258', '346', '440*'],
        ['매출 YoY (%)', '+44', '-4', '+14', '+34', '+27'],
        ['ROE (%)', '2.1', '1.5', '3.9', '8.2', '12.4'],
    ],
}

Q_DICT = {  # 에스엠 실제 형태 (A)
    'headers': ['항목', '2025 1Q', '2025 2Q', '2025 3Q', '2025 4Q'],
    'rows': {'매출액(억원)': [2314, 3029, 3216, 3190],
             '영업이익(억원)': [326, 476, 482, 546]},
}

Q_LIST = {  # AMD 실제 형태 (B)
    'headers': ['항목', "Q3'25", "Q4'25", "Q1'26 가이던스"],
    'rows': [['매출 (억 달러)', '92.5', '102.6', '98G'],
             ['매출 YoY (%)', '+36', '+24', '+32']],
}

Q_TRANSPOSED = {  # GS리테일/삼성전자 실제 형태 (C) -- 첫 열이 분기, headers[1:] 가 지표
    'headers': ['분기', '매출(억)', 'OP(억)', '이슈'],
    'rows': [['1Q25', '27,484', '418', '분할 직후 안정화'],
             ['2Q25', '30,170', '850', '여름 성수기'],
             ['3Q25', '31,200', '1,065', '추석 효과']],
}

# --- _table_rows: 3형태를 (기간, [(지표, 값들)]) 로 정규화 ---
per_a, rows_a = P._table_rows(FIN_DICT)
eq(per_a, ['2022', '2023', '2024', '2025', '2026E'], "(A) dict rows -- 기간 = headers[1:]")
eq(dict(rows_a)['ROE(%)'], [8.1, 9.4, 6.2, 12.0, 12.8], "(A) dict rows -- ROE 행 값")

per_b, rows_b = P._table_rows(FIN_LIST)
eq(per_b, ['FY22', 'FY23', 'FY24', 'FY25', 'FY26E'], "(B) list 지표행 -- 기간 = headers[1:]")
eq(dict(rows_b)['ROE (%)'], ['2.1', '1.5', '3.9', '8.2', '12.4'], "(B) list 지표행 -- ROE 행 값")

per_c, rows_c = P._table_rows(Q_TRANSPOSED)
eq(per_c, ['1Q25', '2Q25', '3Q25'], "(C) 전치 list -- 기간 = rows 첫 열")
eq(dict(rows_c)['매출(억)'], ['27,484', '30,170', '31,200'], "(C) 전치 list -- 지표 = headers[1:]")

eq(P._table_rows({}), ([], []), "빈 표 -> ([], [])")
eq(P._table_rows({'headers': ['항목', '2025'], 'rows': None}), (['2025'], []), "rows=null (에코프로 실제) 안전")
eq(P._table_rows(None), ([], []), "table=None 안전")

# --- _fin_row: 두 자료형 모두 ---
eq(P._fin_row({'financials': FIN_DICT}, 'ROE'),
   (['2022', '2023', '2024', '2025', '2026E'], [8.1, 9.4, 6.2, 12.0, 12.8]),
   "_fin_row dict rows -- ROE")
eq(P._fin_row({'financials': FIN_LIST}, 'ROE'),
   (['FY22', 'FY23', 'FY24', 'FY25', 'FY26E'], [2.1, 1.5, 3.9, 8.2, 12.4]),
   "_fin_row list rows -- ROE (기존 AttributeError 지점)")
eq(P._fin_row({'financials': FIN_LIST}, '없는지표'), (None, None), "_fin_row 미매칭 -> (None, None)")
eq(P._fin_row({}, 'ROE'), (None, None), "_fin_row financials 부재 안전")

# --- b_dupont_roe: list 종목에서 죽지 않고 값을 낸다 ---
eq(P.b_dupont_roe({'financials': FIN_LIST}),
   {'years': ['FY22', 'FY23', 'FY24', 'FY25', 'FY26E'], 'roe': [2.1, 1.5, 3.9, 8.2, 12.4]},
   "b_dupont_roe -- list rows")
eq(P.b_dupont_roe({'financials': FIN_DICT})['roe'], [8.1, 9.4, 6.2, 12.0, 12.8],
   "b_dupont_roe -- dict rows (회귀)")
eq(P.b_dupont_roe({'financials': {'headers': ['항목', '2025'], 'rows': []}}), None,
   "b_dupont_roe -- ROE 행 없으면 None")

# --- b_quarterly_revenue: 3형태 모두 ---
eq(P.b_quarterly_revenue({'quarterly': Q_DICT})['categories'],
   ['2025 1Q', '2025 2Q', '2025 3Q', '2025 4Q'], "b_quarterly_revenue -- dict rows (회귀)")
eq(P.b_quarterly_revenue({'quarterly': Q_LIST})['series']['매출액(억원)'],
   [92.5, 102.6, 98.0], "b_quarterly_revenue -- list 지표행")
eq(P.b_quarterly_revenue({'quarterly': Q_TRANSPOSED})['series']['매출액(억원)'],
   [27484.0, 30170.0, 31200.0], "b_quarterly_revenue -- 전치 list (GS리테일 실제)")
eq(P.b_quarterly_revenue({'quarterly': {'headers': ['항목'], 'rows': []}}), None,
   "b_quarterly_revenue -- 데이터 없으면 None")
eq(P.b_quarterly_revenue({}), None, "b_quarterly_revenue -- quarterly 부재 안전")

# --- b_peer_multiples: 적자/N-A peer 를 None + 라벨로 내보낸다 ---
PEERS = {'meta': {'stock_name': '테스트'},
         'peers': [{'name': '테스트', 'per': '12.5', 'pbr': '1.2', 'highlight': True},
                   {'name': '적자피어', 'per': '적자', 'pbr': '0.8'},
                   {'name': '무자료피어', 'per': 'N/A', 'pbr': '-'}]}
pm = P.b_peer_multiples(PEERS)
eq(pm['per'], [12.5, None, None], "b_peer_multiples -- '적자'/'N/A' -> None (실재 형태)")
eq(pm['per_labels'], [None, '적자', 'N/A'], "b_peer_multiples -- 결측 사유 라벨 동봉")
eq(pm['pbr'][1], 0.8, "b_peer_multiples -- 정상 PBR 유지")
eq(pm['pbr_labels'][2], 'N/A', "b_peer_multiples -- PBR '-' -> N/A 라벨")

# PER/PBR 이 전부 결측이면 도표 자체가 무의미 -> None
allbad = {'meta': {'stock_name': 'X'},
          'peers': [{'name': 'A', 'per': '적자', 'pbr': '적자'},
                    {'name': 'B', 'per': '적자', 'pbr': 'N/A'}]}
eq(P.b_peer_multiples(allbad), None, "b_peer_multiples -- PER/PBR 전부 결측이면 도표 생략")

# --- plan() 회귀: 실제 파일 (list 형 / dict 형) 이 끝까지 돈다 ---
import tempfile
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))


def _plan_in_tmp(analysis_name):
    apath = os.path.join(ROOT, 'scripts', analysis_name)
    if not os.path.exists(apath):
        return None
    cwd = os.getcwd()
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        _, entries = P.plan(apath)
        return entries
    finally:
        os.chdir(cwd)


e_amd = _plan_in_tmp('analysis_AMD.json')
truthy(e_amd, "plan() AMD (rows=list) -- 죽지 않고 도표를 낸다")

e_ss = _plan_in_tmp('analysis_삼성전자.json')   # rows=list 이면서 ROE 행이 실재
truthy(any(x['archetype'] == 'dupont_roe' for x in (e_ss or [])),
       "plan() 삼성전자 (rows=list) -- ROE 도표가 실제로 잡힌다")

e_sm = _plan_in_tmp('analysis_에스엠.json')
truthy(e_sm, "plan() 에스엠 (rows=dict) -- 회귀 없음")
truthy(any(x['archetype'] == 'dupont_roe' for x in (e_sm or [])),
       "plan() 에스엠 (rows=dict) -- ROE 도표 회귀 없음")

print(f"\n{'=' * 60}")
print(f"  wf_chart_planner 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
