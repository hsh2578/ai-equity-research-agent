"""verify_tone -- 문체 지표 (v5.21).

배경: verify_style 100점짜리 리포트를 사용자가 읽고 "AI 티가 난다"고 했다.
기존 검증기는 항목이 있는지만 보고 어떻게 쓰였는지를 안 본다.

여기서 지키는 것은 두 가지다.
  1) 기준선이 **IR협의회 16편 실측**에서 왔다는 것 (임의 숫자가 아니다)
  2) 표 안 볼드와 마진노트 라벨을 강조로 세지 않는 것
     -- 표 헤더를 굵게 쓰는 것은 서식이지 문체가 아니다. 이걸 세면
        표가 많은 리포트가 전부 FAIL 이 나고, 그러면 아무도 안 본다.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from verify_tone import check, measure   # noqa: E402

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


def status(sections, code, order=('s01',)):
    for c, _lab, ok, *_ in check(sections, order)[0]:
        if c == code:
            return ok
    return None


PLAIN = ('동사는 2026년 상반기 매출 1,589억원, 영업이익 **110억원**을 기록했다. '
         '재료부문 매출은 1,048억원으로 전체의 65.9%를 차지한다. '
         '펠리클 내수 판가는 481천원에서 551천원으로 올랐다. ') * 6
NO_BOLD = PLAIN.replace('**', '')

# ---------- T1 볼드 비율 (v5.22: 상한 단독 -> 3~12% 밴드) ----------
eq(status({'s01': PLAIN}, 'T1'), True, '밴드 안(약 5%)이면 통과')
eq(status({'s01': NO_BOLD * 2}, 'T1'), False,
   '**볼드가 아예 없으면 FAIL -- 상한만 두었더니 19.0%에서 0.34%로 갔다**')
eq(status({'s01': PLAIN + '**' + '가' * 400 + '**'}, 'T1'), False,
   '**볼드가 과하면 FAIL -- 교정 전 실측 19.0%였다**')

# ---------- T2 문장 통째 볼드 ----------
long_bold = ''.join(f'**이것은 스물여섯 자가 넘는 아주 긴 강조 문장입니다 번호{i}**\n'
                    for i in range(15))
eq(status({'s01': PLAIN + long_bold}, 'T2'), False,
   '**26자 이상 볼드 15개는 FAIL -- 문장 전체 강조가 AI 티의 주범이었다**')
eq(status({'s01': PLAIN}, 'T2'), True, '긴 볼드가 없으면 통과')

# ---------- 표 안 볼드는 세지 않는다 ----------
tbl = '\n'.join('| **' + '수치' * 30 + '** | 100 |' for _ in range(10))
eq(status({'s01': PLAIN + '\n' + tbl}, 'T1'), True,
   '**표 안 볼드는 서식이지 문체가 아니다 -- 세면 표 많은 리포트가 전부 FAIL 난다**')

# ---------- 마진노트 라벨도 제외 ----------
notes = '\n'.join(f'> **한 줄:** 재료 비중이 {i}% 올랐다' for i in range(12))
eq(status({'s01': PLAIN + '\n' + notes}, 'T1'), True,
   '**`> **한 줄:**` 은 렌더 규약이라 강조로 세지 않는다**')

# ---------- T3 대구 ----------
contr = '이익을 만든 것은 성장이 아니라 교체다. ' * 8
eq(status({'s01': PLAIN + contr}, 'T3'), False,
   '**"A가 아니라 B" 남발은 FAIL -- IR협의회 실측 0.00**')
eq(status({'s01': PLAIN + '원인은 성장이 아니라 믹스 교체다.'}, 'T3'), True,
   '한두 번은 강조로 허용')

# ---------- T4 자의식 표현 ----------
eq(status({'s01': PLAIN + '이 리포트의 중심 질문이다. ' * 4}, 'T4'), False,
   '**"이 리포트의 중심 질문" 같은 메타 발언은 FAIL (실측 0회)**')
eq(status({'s01': PLAIN}, 'T4'), True, '메타 표현이 없으면 통과')

# ---------- T5 유보 표현 (하한) ----------
eq(status({'s01': PLAIN}, 'T5'), False,
   '**단정만 있으면 FAIL -- 추정을 추정이라 적어야 한다**')
eq(status({'s01': PLAIN + '이는 구조적 변화로 판단한다. 2027년 회복을 전망한다. '
                          '반복 발주는 확인이 필요하다. ' * 2}, 'T5'), True,
   '유보 표현이 있으면 통과')

# ---------- T6 시사점 라벨 ----------
eq(status({'s01': PLAIN + '시사점: 어쩌고. ' * 5}, 'T6'), False,
   '"시사점:" 라벨 과다는 FAIL (IR협의회 0회)')

# ---------- T7 재진술 ----------
eq(status({'s01': PLAIN + '그렇다는 뜻이다. 그런 셈이다. ' * 6}, 'T7'), False,
   '"뜻이다/셈이다" 재진술 과다는 FAIL')

# ---------- 입력 방어 ----------
m = measure({}, ())
eq(m['chars'], 1, '빈 입력에서 0 나누기가 나지 않는다')
eq(status({'s01': ''}, 'T1'), True, '빈 섹션은 통과 처리')

# ---------- section_order 밖 섹션은 세지 않는다 ----------
m2 = measure({'s01': PLAIN, 's99': '**' + '가' * 900 + '**'}, ('s01',))
eq(m2['bold_ratio'] < 12.0, True,
   '**order 밖 섹션(alias 사본 등)을 세면 이중 계산이 된다**')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  verify_tone 문체 지표: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
