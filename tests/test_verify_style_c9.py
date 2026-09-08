"""
verify_style C9(100자+ 문장 비율) 문장 분리 테스트 (TDD -- 구현보다 먼저 작성)

배경 (2026-09-08 3종목 실측):
  C9 가 3개 리포트에서 **14회** FAIL 하며 서술 품질 점수를 가장 많이 깎았다.
  그런데 실제 본문을 열어보니 문장이 길어서가 아니라 **분리가 안 돼서**였다.

  기존 분리자: `re.split(r'[.!?]\\s+|[다요]\\.\\s+', prose)`

  두 가지를 못 쪼갠다.

  1. **줄바꿈**. 마크다운 리스트 항목·헤딩·표 캡션이 각각 독립 단위인데
     `\\n` 이 분리자에 없어 통째로 한 "문장" 이 된다.
       "#### 재무 안정성\\n출처: 사업보고서\\n**순현금 0.3조에서 ...**"  -> 1문장(150자+)
  2. **닫는 마크업 뒤 마침표**. 한국어 리포트는 강조 문장을 자주 쓴다.
       "**영업이익 아래에서 두 가지가 벌어졌다.** 당기손익-공정가치측정 ..."
     `다.` 뒤에 공백이 아니라 `**` 가 와서 경계로 인식되지 않는다 -> 2문장이 1문장.

  실측: 3개 리포트 15개 섹션에서 100자+ 문장이 **60개 -> 30개(-50%)**.
  즉 C9 실패의 절반이 서술 문제가 아니라 계측 문제였다.

  이 검증기는 "영문 직역체" 를 잡으라고 만든 것이다. 마크다운 구조를 문장으로
  세면 한국어로 잘 쓴 리포트도 직역체로 판정된다 -- 게이트의 취지와 반대다.

주: split_sentences 의 기본 min_len=20 은 실제 계측용 필터다.
    아래 짧은 단위 예시는 min_len=0 으로 분리 로직만 검증한다.

실행: python tests/test_verify_style_c9.py
"""
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from verify_style import split_sentences, check_c9_long_sentence

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def close(actual, expected, name, tol=0.5):
    global _passed
    if abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


# --- 기본 분리 ---
eq(len(split_sentences('첫 문장이다. 두 번째 문장이다. 세 번째 문장이다.', min_len=0)), 3,
   "마침표 + 공백으로 분리")
eq(len(split_sentences('첫 줄이다\n둘째 줄이다\n셋째 줄이다', min_len=0)), 3,
   "**줄바꿈으로도 분리한다** (마크다운 리스트/헤딩)")

# --- 닫는 마크업 뒤 마침표 ---
eq(len(split_sentences('**강조된 문장이다.** 이어지는 문장이다.', min_len=0)), 2,
   "볼드 닫힘 뒤 마침표도 경계 (`다.**`)")
eq(len(split_sentences('*기울임이다.* 다음 문장이다.', min_len=0)), 2, "이탤릭 닫힘")
eq(len(split_sentences('`코드다.` 다음 문장이다.', min_len=0)), 2, "백틱 닫힘")
eq(len(split_sentences('(괄호 안이다.) 다음 문장이다.', min_len=0)), 2, "괄호 닫힘")
eq(len(split_sentences('"인용이다." 다음 문장이다.', min_len=0)), 2, "따옴표 닫힘")

# --- 소수점은 문장 경계가 아니다 ---
eq(len(split_sentences('영업이익이 95.8억이고 세율은 39.1%였다.', min_len=0)), 1,
   "소수점은 쪼개지 않는다 (뒤에 공백이 없다)")
eq(len(split_sentences('매출은 5,454.0억이다. 영업이익은 713.4억이다.', min_len=0)), 2,
   "소수점 있어도 문장 끝은 정상 분리")

# --- 실측 재현: 볼드 강조 문장 ---
real = ('**영업이익 아래에서 두 가지가 벌어졌다.** 당기손익-공정가치측정 금융자산 '
        '평가손실이 상반기 95.8억(전년 동기 0.04억)이었고, 유효세율이 19.1%에서 '
        '**39.1%**로 뛰었다.')
parts = split_sentences(real)
eq(len(parts), 2, "실측 문장이 2개로 분리된다 (기존 구현은 1개 104자로 셌다)")
eq(all(len(p) <= 100 for p in parts), True, "분리 후 두 조각 모두 100자 이하")

# --- 마크다운 블록 ---
md = """#### 재무 안정성 -- 순현금이 반년 만에 줄었다
출처: FnGuide 재무상태표(2026/06)
**순현금 0.3조에서 2,361억으로 15.6% 줄었다.** 그런데 현금이 사라진 게 아니라 옮겨갔다."""
parts = split_sentences(md)
eq(len(parts) >= 4, True, "헤딩/출처줄/본문이 각각 분리된다")
eq(all(len(p) <= 100 for p in parts), True, "마크다운 블록도 전부 100자 이하로 쪼개진다")

# --- C9 종합: 마크다운 구조가 100자+ 로 오판되지 않는다 ---
pct, cnt = check_c9_long_sentence(md)
eq(cnt, 0, "마크다운 블록에서 100자+ 문장 0개")

# --- 진짜 긴 문장은 여전히 잡는다 (게이트가 무력화되면 안 된다) ---
long_one = ('이 회사는 반도체 소재를 만들며 최근 몇 년간 지속적으로 매출이 증가해 왔고 '
            '동시에 영업이익률 또한 개선되는 흐름을 보이면서 시장의 기대를 모으고 있는데 '
            '다만 경쟁 심화와 원가 상승이라는 구조적 부담도 함께 안고 있는 상황이다.')
eq(len(long_one) > 100, True, "(전제) 테스트 문장이 100자를 넘는다")
pct2, cnt2 = check_c9_long_sentence(long_one)
eq(cnt2, 1, "**진짜 긴 문장은 여전히 잡는다**")

# 표/코드는 계측에서 제외된다 (기존 동작 유지)
tbl = '| 항목 | 값 |\n|---|---|\n| 매출 | 5,454억 |\n짧은 문장이다.'
pct3, cnt3 = check_c9_long_sentence(tbl)
eq(cnt3, 0, "표 행은 문장으로 세지 않는다")

# 빈 입력
eq(check_c9_long_sentence(''), (0, 0), "빈 문자열은 (0, 0)")
eq(check_c9_long_sentence('짧다.'), (0, 0), "20자 이하만 있으면 (0, 0)")

print(f"\n{'=' * 60}")
print(f"  verify_style C9 문장 분리 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
