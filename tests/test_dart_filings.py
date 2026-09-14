"""collect_dart_filings -- 어떤 공시의 본문을 받을지 고르는 규칙.

배경(2026-09 에프에스티): 정기보고서만 읽고 리포트를 썼더니 "설비투자 목적을
공시가 말하지 않는다"고 쓰게 됐다. 자기주식처분결정 공시에
"처분목적: EUV펠리클 확장 투자 재원 확보"라고 적혀 있었다.

여기서 검증하는 것은 **필터**다. 필터가 한 종류라도 놓치면 그 공시는
수집 자체가 안 되고, 없는 자료는 리포트에도 없다.
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from collect_dart_filings import wants_body   # noqa: E402

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


# ---------- 본문을 받아야 하는 것 (전부 에프에스티 실제 공시명) ----------
eq(wants_body('주요사항보고서(자기주식처분결정)'), True,
   "**자기주식처분결정 -- 처분목적에 투자 용처가 적힌다**")
eq(wants_body('자기주식처분결과보고서'), True, '자기주식 처분 결과')
eq(wants_body('주식소각결정'), True,
   "**주식소각 -- 발행주식수가 바뀌면 주당 지표가 전부 바뀐다**")
eq(wants_body('매출액또는손익구조30%(대규모법인은15%)이상변동'), True,
   "**실적변동 공시 -- 회사가 적자 사유를 직접 적는다**")
eq(wants_body('소속부변경'), True, '소속부 변경 (우량 -> 중견)')
eq(wants_body('주요사항보고서(교환사채권발행결정)'), True, '교환사채 (희석 요인)')
eq(wants_body('주요사항보고서(회사합병결정)'), True, '합병')
eq(wants_body('단일판매ㆍ공급계약체결'), True, '공급계약 (수주)')
eq(wants_body('신규시설투자등'), True, '시설투자')
eq(wants_body('기업설명회(IR)개최'), True, 'IR 개최 (자료 존재 신호)')
eq(wants_body('현금ㆍ현물배당결정'), True, '현금배당')
eq(wants_body('주식배당결정'), True, '주식배당')
eq(wants_body('타법인주식및출자증권취득결정'), True, '타법인 출자 (관계기업 변동)')
eq(wants_body('기업가치제고계획'), True, '밸류업 계획')

# 띄어쓰기가 섞여 들어와도 걸러야 한다 (DART 표기가 일정하지 않다)
eq(wants_body('주요사항보고서(자기주식 처분 결정)'), True,
   '**띄어쓰기 변형 -- DART 표기는 일정하지 않다**')

# ---------- 본문이 필요 없는 것 ----------
eq(wants_body('주주명부폐쇄기간또는기준일설정'), False, '주주명부 폐쇄 (정보 없음)')
eq(wants_body('주주총회소집공고'), False, '주총 소집공고')
eq(wants_body('의결권대리행사권유참고서류'), False, '의결권 대리행사')
eq(wants_body('감사보고서제출'), False, '감사보고서 제출 (별도 수집)')
eq(wants_body('독립이사의선임ㆍ해임또는중도퇴임에관한신고'), False, '이사 선임')

# 정기보고서는 collect_dart_full.py 담당이라 여기서는 받지 않는다
eq(wants_body('사업보고서 (2025.12)'), False, '정기보고서는 collect_dart_full 담당')
eq(wants_body('반기보고서 (2026.06)'), False, '반기보고서도 동일')
eq(wants_body('분기보고서 (2026.03)'), False, '분기보고서도 동일')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  DART 수시공시 필터: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
