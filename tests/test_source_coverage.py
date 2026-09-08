"""source_coverage -- 1차 출처에 있는데 본문이 안 쓴 것을 잡는가.

이 검증기가 있어야 하는 이유(2026-09-08 LS일렉트릭 v1 실측):
리포트가 verify_numbers / verify_facts / preflight 를 전부 통과하고
verify_style 99점을 받았는데 결론이 틀렸다. 결정적 근거 셋(영업활동현금흐름
-819.9억 / 부문정보 연결조정 / 진행기준 추정변경 +278억)이 **이미 내려받은
반기보고서 안**에 있었는데 본문이 한 줄도 쓰지 않았다.

기존 검증기는 "쓴 숫자가 맞는가"를 본다. 이 검증기는 "써야 할 것을 봤는가"를 본다.

거짓 FAIL 이 나면 아무도 안 보게 되므로, 오탐 케이스를 함께 고정한다.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from source_coverage import check, PROBES   # noqa: E402

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def status_of(rows, key):
    for k, _, st, _why in rows:
        if k == key:
            return st
    return None


# ---------- 핵심 동작 ----------
SRC_FULL = (
    '연결 현금흐름표\n영업활동으로 인한 현금흐름 (81,987,921,486)\n'
    '부문정보 ... 연결조정 (1,047,792)\n'
    '추정총계약수익의 변동 51,727\n'
    '다. 수주 상황 ... 수주잔고 68,896\n'
    '(2) 당반기말 평균가동률 96.4\n'
    '나. 제품 가격변동 추이 차단기 118\n'
    '(3) 연구개발비용 합 계 84,742\n'
    '최대주주 및 특수관계인의 주식소유 현황\n'
)
BODY_GOOD = (
    '영업활동현금흐름은 -819.9억원이다. 부문정보를 보면 연결조정이 있다. '
    '추정 변경이 당기 손익에 반영됐다. 수주잔고 7조원. 가동률 96.4%. '
    '기준가는 4년간 +2.6%. 연구개발비는 매출의 2.9%. 최대주주 지분 48.46%.'
)
rows = check(SRC_FULL, BODY_GOOD)
eq([r[2] for r in rows].count('FAIL'), 0, "출처의 것을 본문이 다 쓰면 FAIL 0")
eq([r[2] for r in rows].count('WARN'), 0, "want 항목도 다 쓰면 WARN 0")

rows = check(SRC_FULL, '수주잔고가 7조원으로 늘었다. 가동률과 연구개발과 최대주주 지분도 썼다.')
eq(status_of(rows, 'cashflow'), 'FAIL', "**현금흐름표가 있는데 본문이 안 쓰면 FAIL**")
eq(status_of(rows, 'segment'), 'FAIL', "부문정보가 있는데 안 쓰면 FAIL")
eq(status_of(rows, 'poc'), 'FAIL', "진행기준 추정변경이 있는데 안 쓰면 FAIL")
eq(status_of(rows, 'backlog'), 'PASS', "쓴 것은 PASS")

# ---------- 없는 것을 벌하지 않는다 ----------
rows = check('아무 내용도 없는 사업보고서', '본문')
eq([r[2] for r in rows].count('SKIP'), len(PROBES),
   "출처에 없으면 전부 SKIP -- 공시 안 한 회사를 벌하지 않는다")
eq([r[2] for r in rows].count('FAIL'), 0, "SKIP 은 FAIL 이 아니다")

# ---------- 오탐 방지 (실측 케이스) ----------
# 1) '회계추정의 변경' 은 모든 주석에 있는 보일러플레이트
BOILER = ('유형자산의 감가상각방법, 잔존가치 및 내용연수는 매 보고기간말에 재검토하고 '
          '있으며, 이를 변경하는 것이 적절하다고 판단되는 경우 회계추정의 변경으로 '
          '회계처리하고 있습니다.')
eq(status_of(check(BOILER, '본문'), 'poc'), 'SKIP',
   "'회계추정의 변경' 보일러플레이트를 진행기준 계약으로 오인하지 않는다")

# 2) 위험관리 서술문의 '영업활동현금흐름' 은 현금흐름표가 아니다
NARRATIVE = ('당사의 경영진은 영업활동현금흐름과 금융자산의 현금유입으로 '
             '금융부채를 상환가능하다고 판단하고 있습니다.')
eq(status_of(check(NARRATIVE, '본문'), 'cashflow'), 'SKIP',
   "서술문 속 '영업활동현금흐름' 을 재무제표로 오인하지 않는다")

# 3) 숫자가 붙은 실제 표는 잡는다
eq(status_of(check('영업활동현금흐름 10,346,383,084', '본문'), 'cashflow'), 'FAIL',
   "금액이 붙은 실제 표는 잡는다")

# ---------- 등급 구분 ----------
eq(status_of(check('평균가동률 96.4', '본문'), 'utilization'), 'WARN',
   "want 등급은 FAIL 이 아니라 WARN")
eq(status_of(check('연결조정 (1,047,792)', '본문'), 'segment'), 'FAIL',
   "must 등급은 FAIL")

# ---------- 입력 방어 ----------
eq([r[2] for r in check('', '')].count('SKIP'), len(PROBES), "빈 입력은 전부 SKIP")
eq([r[2] for r in check(None, None)].count('SKIP'), len(PROBES), "None 도 안전")

print('=' * 62)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  source_coverage 1차 출처 활용도: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 62)
sys.exit(1 if _failed else 0)
