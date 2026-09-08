"""fleet_audit -- 전 종목 x 검증기 표를 만드는 도구.

배경(2026-09-09): v5.20 규칙 1("새 검증기는 그날 안에 전 종목에 돌린다")을
규칙으로만 적어 두면 또 빠뜨린다. 손으로 하던 루프를 도구로 만들었다.

여기서 검증하는 것은 **출력 파싱**이다. 검증기마다 FAIL 표기 형식이 달라
(`FAIL 3건` / `총 FAIL: 2` / `총 D 블록 FAIL ...: 1`) 하나만 보면 조용히
'판정 불가'가 되고, 그러면 결함이 있는데도 표가 깨끗해 보인다.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from fleet_audit import parse_fail, is_us   # noqa: E402

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


# ---------- 검증기별 FAIL 표기 (전부 실제 출력 형식) ----------
eq(parse_fail('  FAIL 0건 / WARN 2건'), 0, "section_rubric 형식 -- 0건")
eq(parse_fail('  FAIL 7건 / WARN 4건'), 7, "section_rubric 형식 -- 7건")
eq(parse_fail('총 FAIL: 0건'), 0, "verify_numbers(KR) 형식")
eq(parse_fail('총 FAIL: 2 / WARN: 1 / 전체 체크: 19'), 2, "verify_numbers_us 형식")
eq(parse_fail('총 D 블록 FAIL (B19~B22+D5+D6 포함 v5.2): 3'), 3,
   "**verify_facts 형식 -- 이걸 못 읽으면 팩트 결함이 통째로 안 보인다**")
eq(parse_fail('[OK] 팩트 체크 통과. report-critic 서브에이전트 호출 가능.'), 0,
   "FAIL 숫자가 없고 [OK] 만 있으면 0")

# ---------- 판정 불가 ----------
eq(parse_fail('[SKIP] data/LS/ 에 DART/SEC 전문 덤프가 없다.'), None,
   "SKIP 은 0 이 아니라 판정 불가다 -- 0 으로 세면 깨끗해 보인다")
eq(parse_fail(''), None, "빈 출력은 판정 불가")
eq(parse_fail(None), None, "None 도 안전")
eq(parse_fail('[ERR] analysis.json 없음'), None, "에러도 판정 불가")

# ---------- KR/US 분기 ----------
# meta.country 를 먼저 본다. data_kis_us.json 만 보면 US 종목에 KR 검증기가 돈다
# (LULU 실측 -- 그 파일이 없는데 verify_numbers_us 는 정상 동작했다)
eq(is_us('BE'), True, "meta.country=US 면 US")
eq(is_us('LULU'), True, "**data_kis_us.json 이 없어도 meta.country 로 US 판정**")
eq(is_us('삼성SDI'), False, "meta.country=KR 이면 KR")
eq(is_us('없는종목'), False, "없는 종목은 KR 기본값 (파일 폴백)")

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  fleet_audit 출력 파싱: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
