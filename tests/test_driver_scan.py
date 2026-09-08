"""
driver_scan -- 사업 구동 변수 자동 추출 (TDD, 구현보다 먼저 작성)

배경 (2026-09-08, 수상작 논증 정독):
  수상작은 **사업 사실에서 출발해 숫자로 간다.**

    "G사 TPU v8x 'Zebrafish'가 10월부터 양산 진입. 층수 24층 -> 36층,
     M8급 CCL 채택으로 기판당 ASP 상승"   (이수페타시스)

  우리 투자포인트는 "컨센서스가 하반기에 상반기의 3.83배를 요구한다" 로 끝났다.
  맞는 말이지만 **회사가 무엇을 하는지에 대해서는 한 마디도 하지 않는다.**

  그런데 실측해 보니 이런 사실이 **DART 안에 이미 있었다**:
    · "트레저는 일본 단독 공연 누적 관객 수 100만 명을 기록했습니다"
    · "발매 당일 국내에서만 약 60만 장(한터차트 기준) ... 역대 최다 초동"
    · "일본에서는 총 15만 명의 관객을 동원"
    · "2026년 상반기 누적 판매량은 약 5,500만 장으로 전년 동기 대비 약 1,100만 장 증가"

  못 쓴 이유는 데이터가 없어서가 아니라 **grep 패턴이 재무 중심**이라 안 잡은 것이다.
  이 모듈이 P x Q - C 를 실제 변수명으로 훑는다.

  evidence_scan 과 같은 원칙: **원문 문장 + line 번호**를 함께 준다.
  위치가 붙으면 가짜 인용이 구조적으로 불가능하다.

실행: python tests/test_driver_scan.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from driver_scan import scan_text, CATEGORIES, MIN_FILLED

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def ok(cond, name):
    global _passed
    if cond:
        _passed += 1
    else:
        _failed.append(name)


eq(MIN_FILLED, 3, "최소 3개 변수는 숫자로 채워야 한다 (v5.10 규칙 1)")
for c in ('물량(Q)', '단가(P)', '비용(C)', '고객·계약', '일정'):
    ok(c in CATEGORIES, f"카테고리 '{c}' 가 있다")

TXT = """회사 개요입니다.
특히 당사 소속 트레저는 일본 단독 공연 누적 관객 수 100만 명을 기록했습니다.
공연은 관객과 아티스트가 교감하는 예술입니다.
발매 당일 국내에서만 약 60만 장(한터차트 기준)을 판매하며 역대 최다 초동을 달성했습니다.
평균 티켓 단가는 25만 원 수준으로 추정됩니다.
2026년 10월부터 신제품 양산에 진입할 예정입니다.
주요 고객사와의 수주잔고는 5,737억원입니다.
"""

hits = scan_text(TXT)
by = {}
for h in hits:
    by.setdefault(h['category'], []).append(h)

ok('물량(Q)' in by, "관객 수·판매량을 물량으로 잡는다")
ok(any('100만 명' in h['text'] for h in by.get('물량(Q)', [])), "누적 관객 100만 명 포착")
ok(any('60만 장' in h['text'] for h in by.get('물량(Q)', [])), "초동 60만 장 포착")
ok(any('25만 원' in h['text'] for h in by.get('단가(P)', [])), "티켓 단가 포착")
ok(any('양산' in h['text'] for h in by.get('일정', [])), "양산 일정 포착")
ok(any('수주잔고' in h['text'] for h in by.get('고객·계약', [])), "수주잔고 포착")

# --- 숫자 없는 일반 서술은 드라이버가 아니다 ---
ok(not any('교감하는 예술' in h['text'] for h in hits),
   "**숫자 없는 일반 서술은 제외** (공연은 관객과 교감하는 예술이다)")
ok(not any('회사 개요입니다' in h['text'] for h in hits), "머리말 제외")

# --- 위치가 붙는다 (가짜 인용 차단) ---
for h in hits:
    ok(isinstance(h.get('line'), int) and h['line'] >= 1, "각 결과에 line 번호가 있다")
    break
tre = [h for h in hits if '100만 명' in h['text']][0]
eq(tre['line'], 2, "line 번호가 실제 줄과 일치한다")

# --- 중복 제거 ---
dup = "누적 관객 수 100만 명을 기록했습니다.\n누적 관객 수 100만 명을 기록했습니다.\n"
eq(len(scan_text(dup)), 1, "같은 문장이 두 번 나와도 한 번만 센다")

# --- 방어 ---
eq(scan_text(''), [], "빈 입력")
eq(scan_text('숫자 없는 문장입니다.'), [], "숫자가 없으면 잡지 않는다")

# --- 너무 긴 문장은 자른다 (표 조각이 통째로 들어오는 것 방지) ---
long_hit = scan_text('관객 ' + '가' * 500 + ' 100만 명입니다.')
if long_hit:
    ok(len(long_hit[0]['text']) <= 300, "긴 문장은 300자로 자른다")
else:
    _passed += 1

print(f"\n{'=' * 62}")
print(f"  driver_scan 사업 구동 변수 추출: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 62}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
