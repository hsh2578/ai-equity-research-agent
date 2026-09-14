"""wisereport_consensus -- 분기를 연간으로 읽지 않는다 (v5.21).

배경: 임시 코드가 4분기 컨센서스(영업이익 88억)를 연도 키(202612)에 저장했고,
리포트가 "상반기 확정 110억이 연간 컨센 88억을 이미 넘었다 -- 컨센이 갱신되지
않는다"고 썼다. 실제 2026년 연간 컨센은 277억이며 3개월 전 231억에서
**상향**된 값이었다. 라벨 하나 때문에 결론이 정반대로 나갔다.

그래서 여기서 지키는 것:
  1) 값에 period_type 이 붙는다 (분기를 연간으로 쓰는 것이 불가능해진다)
  2) 추이 컬럼(현재/1주전/1개월전/3개월전/1년전)이 순서대로 붙는다
  3) min==max 면 '추정 기관 1곳'으로 표시된다 -- 그때 '평균'이라 쓰면 거짓이다
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from wisereport_consensus import COLS, parse_table, parse_trend   # noqa: E402

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


# 실제 응답 형태 (2026-09-14 에프에스티 036810)
ANNUAL = {'JsonData': [
    {'SEQ': 2, 'ACC_CD': '121000', 'ACC_NM': '매출액(억원)',
     'VAL1': 3363.0, 'VAL2': 3363.0, 'VAL3': 0.0, 'VAL4': 3070.0, 'VAL5': 0.0},
    {'SEQ': 3, 'ACC_CD': '121500', 'ACC_NM': '영업이익(억원)',
     'VAL1': 277.0, 'VAL2': 277.0, 'VAL3': 0.0, 'VAL4': 231.0, 'VAL5': 0.0},
    {'SEQ': 5, 'ACC_CD': '312000', 'ACC_NM': 'EPS(원)',
     'VAL1': 611.2186, 'VAL2': 611.2186, 'VAL3': None, 'VAL4': 422.79783, 'VAL5': None},
]}
QUARTER = {'JsonData': [
    {'SEQ': 3, 'ACC_CD': '121500', 'ACC_NM': '영업이익(억원)',
     'VAL1': 88.0, 'VAL2': 88.0, 'VAL3': 0.0, 'VAL4': 114.0, 'VAL5': 0.0},
]}

a = parse_table(ANNUAL)
q = parse_table(QUARTER)

eq(a['영업이익(억원)']['현재'], 277.0, '연간 영업이익 컨센은 277억이다')
eq(q['영업이익(억원)']['현재'], 88.0,
   '**88억은 분기 값이다 -- 같은 파서가 연간과 분기를 섞지 않는다**')
eq(a['영업이익(억원)']['3개월전'], 231.0,
   '**3개월 전 231억 -> 지금 277억. 추이를 봐야 "갱신 안 됐다"를 말할 수 있다**')
eq(list(a['매출액(억원)']), list(COLS),
   'VAL1~VAL5 가 현재/1주전/1개월전/3개월전/1년전 순서로 붙는다')
eq(COLS[0], '현재', '첫 열은 조회 시점 값이다')

# ACC_NM 이 없는 행은 버린다 (빈 행이 키 None 으로 들어가면 표가 깨진다)
eq(parse_table({'JsonData': [{'SEQ': 1, 'ACC_NM': None, 'VAL1': 1}]}), {},
   '항목명 없는 행은 무시한다')
eq(parse_table({}), {}, '빈 응답에서 죽지 않는다')

# ---------- 추이 + 추정기관 수 ----------
TREND = {
    'chart1': json.dumps({'item_unit': '원', 'item_name': 'EPS',
                          'categories': ['2026/06/30', '2026/09/14'],
                          'avg': [422.80, 611.22],
                          'min_max': [[422.80, 422.80], [611.22, 611.22]]}),
    'chart2': json.dumps({'item_unit': '억원', 'item_name': '영업이익',
                          'categories': ['2026/06/30', '2026/09/14'],
                          'avg': [231.00, 277.00],
                          'min_max': [[200.00, 260.00], [250.00, 300.00]]}),
}
t = parse_trend(TREND)
eq(t['EPS']['single_estimator'], True,
   '**min==max 면 추정 기관이 1곳이다 -- 이때 "컨센서스 평균"이라 쓰면 거짓이다**')
eq(t['영업이익']['single_estimator'], False, '범위가 있으면 복수 기관이다')
eq(t['영업이익']['avg'], [231.0, 277.0], '추이 값이 시점 순서대로 들어온다')
eq(parse_trend({'chart1': json.dumps({'categories': [], 'avg': []})}), {},
   '**빈 차트는 항목으로 만들지 않는다 -- 빈 껍데기가 "데이터 있음"으로 읽힌다**')
eq(parse_trend({}), {}, '빈 응답에서 죽지 않는다')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  wisereport_consensus 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
