"""ta_calendar 테스트 (Task 6).

날짜 계산·정규식 추출은 순수 함수라 네트워크·파일 I/O 없이 픽스처만으로 돈다.
today 는 모든 테스트에서 고정한다 (2026-09-17).

실행: python tests/test_ta_calendar.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from datetime import date               # noqa: E402
import ta_calendar as tac                # noqa: E402

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


TODAY = date(2026, 9, 17)

# ---------- 1. 법정 제출기한 ----------
deadlines = {d['event']: d['date'] for d in tac.statutory_deadlines(TODAY)}
eq(deadlines['3분기 분기보고서 제출기한'], date(2026, 11, 14),
   'today=2026-09-17 -> 3분기 분기보고서 2026-11-14')
eq(deadlines['반기보고서 제출기한'], date(2027, 8, 14), '반기보고서: 이번해 8/14 이미 지났으면 내년')
eq(deadlines['사업보고서 제출기한'], date(2027, 3, 31), '사업보고서: 12월말+90일')

eq(tac.fiscal_year_end_ok(None), (True, None), '결산월 정보 없으면 12월 결산으로 가정하고 진행')
eq(tac.fiscal_year_end_ok('12월')[0], True, '결산월 12월이면 통과')
ok, reason = tac.fiscal_year_end_ok('6월')
eq(ok, False, '결산월이 12월이 아니면 법정기한 규칙을 건너뛴다')
eq('6월' in reason, True, '건너뛴 사유에 결산월 값을 남긴다')

# ---------- 2. 전년 패턴 (+1년, 주말 보정) ----------
eq(tac.adjust_weekend(date(2026, 9, 8)), date(2026, 9, 8), '평일(화)은 그대로')
eq(tac.adjust_weekend(date(2026, 9, 5)), date(2026, 9, 7), '토요일 -> 다음 월요일')
eq(tac.adjust_weekend(date(2026, 9, 6)), date(2026, 9, 7), '일요일 -> 다음 월요일')

# 2025-09-05(금) + 1년 = 2026-09-05(토) -> 2026-09-07(월) 로 보정
filings_list = [{'date': '20250905', 'name': '기업설명회(IR)개최(안내공시)', 'rcept_no': 'R1'}]
py_items = tac.prior_year_items(filings_list)
eq(len(py_items), 1, '기업설명회(IR)개최 패턴 1건 인식')
eq(py_items[0]['date'], date(2026, 9, 7), '+1년 후 토요일이면 다음 월요일로 보정')
eq(py_items[0]['ref'], 'R1', '원 공시 rcept_no 를 source ref 로')

# 잠정실적/주총소집결의도 인식, 무관한 공시는 무시
filings_list2 = [
    {'date': '20250811', 'name': '연결재무제표기준영업(잠정)실적(공정공시)', 'rcept_no': 'R2'},
    {'date': '20250310', 'name': '주주총회소집결의              (임시주주총회)', 'rcept_no': 'R3'},
    {'date': '20250101', 'name': '소속부변경', 'rcept_no': 'R4'},
]
py_items2 = tac.prior_year_items(filings_list2)
eq(len(py_items2), 2, '잠정실적/주총소집결의만 인식하고 무관한 공시는 건너뛴다')
eq({it['event'] for it in py_items2}, {'잠정실적 발표 예상(전년 패턴)', '주주총회소집결의 예상(전년 패턴)'},
   '이름 뒤 공백·괄호가 섞여도 접두 정규화 후 매칭')

# ---------- 3. 공백 섞인 날짜 파싱 3형식 + 공시명 정규화 ----------
for label, txt in [
    ('공백형', '4. 배당기준일 \n 2026 년 08 월 27 일'),
    ('붙임형', '4. 배당기준일 \n 2026년 08월 27일'),
    ('점형', '4. 배당기준일 \n 2026.08.27'),
]:
    bodies = [{'name': '[기재정정]현금ㆍ현물배당결정   ', 'rcept_no': 'D1', 'text': txt}]
    items = tac.disclosure_items(bodies)
    eq(len(items), 1, f'배당기준일 {label} 날짜 파싱')
    if items:
        eq(items[0]['date'], date(2026, 8, 27), f'배당기준일 {label} -> 2026-08-27')

eq(tac.normalize_filing_name('[기재정정]현금ㆍ현물배당결정   '), '현금ㆍ현물배당결정',
   '접두 [기재정정] 제거 + 끝 공백 strip')
eq(tac.normalize_filing_name('주주총회소집결의              (임시주주총회)'),
   '주주총회소집결의 (임시주주총회)', '내부 연속 공백은 한 칸으로 축소')

# 대시형(2026-08-27)도 파싱
bodies_dash = [{'name': '현금ㆍ현물배당결정', 'rcept_no': 'D2', 'text': '4. 배당기준일\n2026-08-27'}]
eq(tac.disclosure_items(bodies_dash)[0]['date'], date(2026, 8, 27), '대시형(YYYY-MM-DD)도 파싱')

# ---------- 4. 전환청구기간 시작·종료 둘 다 + quote ----------
cb_text = (
    '2) 전환대상 주식의 기산일 가중산술평균주가\n\n 전환청구기간\n 시작일\n2026년 10월 02일\n\n'
    ' 종료일\n2031년 08월 25일\n\n 전환가액 조정에 관한 사항'
)
cb_bodies = [{'name': '주요사항보고서(전환사채권발행결정)', 'rcept_no': 'B1', 'text': cb_text}]
cb_items = tac.disclosure_items(cb_bodies)
eq(len(cb_items), 2, '전환청구기간 시작·종료 두 건 모두 추출')
starts = [i for i in cb_items if i['event'].endswith('시작')]
ends = [i for i in cb_items if i['event'].endswith('종료')]
eq(starts[0]['date'], date(2026, 10, 2), '전환청구기간 시작일')
eq(ends[0]['date'], date(2031, 8, 25), '전환청구기간 종료일')
eq('2026년 10월 02일' in starts[0]['quote'], True, '시작일 quote 에 원문 날짜 포함')
eq(starts[0]['ref'], 'B1', 'rcept_no 를 source ref 로')

# 교환청구기간 / 처분예정기간 / 취득예정기간도 동일 패턴으로 동작
eb_bodies = [{'name': '주요사항보고서(교환사채권발행결정)', 'rcept_no': 'B2',
              'text': '교환청구기간\n 시작일\n2026년 01월 01일\n\n 종료일\n2030년 12월 31일'}]
eq(len(tac.disclosure_items(eb_bodies)), 2, '교환청구기간도 시작·종료 두 건')

disp_bodies = [{'name': '주요사항보고서(자기주식처분결정)', 'rcept_no': 'B3',
                'text': '4. 처분예정기간\n 시작일\n2026년 09월 20일\n\n 종료일\n2026년 09월 25일'}]
disp_items = tac.disclosure_items(disp_bodies)
eq(len(disp_items), 2, '처분예정기간도 시작·종료 두 건')
eq(disp_items[0]['event'], '자기주식 처분 시작', '자기주식 처분 이벤트명')

# ---------- 주총 일시 / IR 일시 (이름으로 구분) ----------
agm_bodies = [{'name': '주주총회소집공고', 'rcept_no': 'M1',
               'text': '1. 회의의 목적사항\n\n2. 일 시\n2026년 11월 10일 10시\n\n3. 장소\n본사'}]
agm_items = tac.disclosure_items(agm_bodies)
eq(len(agm_items), 1, '주총 일시 1건')
eq(agm_items[0]['event'], '주주총회 개최', '정기/임시 구분 없으면 일반 라벨')
eq(agm_items[0]['date'], date(2026, 11, 10), '주총 개최일 파싱')

ir_bodies = [{'name': '기업설명회(IR)개최(안내공시)', 'rcept_no': 'M2',
              'text': '1. 일시\n 행사일\n\n 시작일\n2026-11-05\n 종료일\n2026-11-05'}]
ir_items = tac.disclosure_items(ir_bodies)
eq(len(ir_items), 1, 'IR 일시 1건(표 헤더를 건너뛰고 첫 날짜를 잡는다)')
eq(ir_items[0]['event'], '기업설명회(IR) 개최', 'IR 개최 이벤트명')
eq(ir_items[0]['date'], date(2026, 11, 5), 'IR 개최일 파싱')

# ---------- 5. 뉴스 "11월 5일" 연도 추론 (fix round 1) ----------
# 무연도 "M월 D일" 은 today 가 아니라 **기사 발행일**(datetime) 기준으로 해를 고른다.
news_items = [
    {'nid': 'N1', 'title': '회사, 신규 라인 11월 5일 가동 예정', 'body': '',
     'datetime': '2026-08-01T09:00:00+09:00', 'relevant': True},
    {'nid': 'N3', 'title': '2027년 3월 2일 증설 목표로 공장 착공', 'body': '',
     'datetime': '2026-06-01T09:00:00+09:00', 'relevant': True},
]
ncal = tac.news_calendar_items(news_items, TODAY)
eq(len(ncal), 2, '뉴스 2건에서 날짜 각 1개씩 추출')
dates = sorted(i['date'] for i in ncal)
eq(dates, [date(2026, 11, 5), date(2027, 3, 2)], '연도 없는 "11월 5일"은 발행일 이후 가장 가까운 해로 추론')
eq(any(i['ref'] == 'N1' for i in ncal), True, 'nid 를 source ref 로')

# relevant == false 는 날짜·맥락이 다 맞아도 제외
irrelevant = [{'nid': 'NR', 'title': '신규 라인 11월 5일 가동 예정', 'body': '',
               'datetime': '2026-08-01T09:00:00+09:00', 'relevant': False}]
eq(tac.news_calendar_items(irrelevant, TODAY), [], 'relevant=False 기사는 제외')

# ---------- 실제 사고 재현 3건 (컨트롤러 fix round 1 보고) -- 전부 제외돼야 한다 ----------
real_bugs = [
    # (1) 시황/공시 집계 기사 제목 자체가 '일정'이 아니라 '결과' 보도
    {'nid': 'B1', 'title': '9월 17일 주식시장 주요공시', 'body': '오늘 공시된 내용을 정리했다.',
     'datetime': '2026-09-17T08:00:00+09:00', 'relevant': True},
    # (2) 등락 결과 보도 -- ta_common.is_reaction_title 이 걸러야 한다('주가 ', '장중')
    {'nid': 'B2', 'title': '에프에스티, 주가 1월 22일 장중 39,250원 25.00% 상승', 'body': '',
     'datetime': '2026-01-22T10:00:00+09:00', 'relevant': True},
    # (3) 발행일 그 자체를 가리키는 언급 -- 미래 일정이 아니라 그날 있었던 일의 보도
    {'nid': 'B3', 'title': '에프에스티, 임직원 상여금 지급 위해 자기주식 처분 결정',
     'body': '회사는 1월 29일 이사회를 열고 자기주식 처분을 결정했다고 공시했다.',
     'datetime': '2026-01-29T09:00:00+09:00', 'relevant': True},
    # (4) 실 데이터(에프에스티 N0248)로 라이브 실행하다 새로 발견한 오탐 -- 앞 문장의
    # "예정"(소각 예정 금액) 이 마침표 너머 다음 문장의 무관한 날짜(3월9일 종가 기준일)에
    # 달라붙어 2027-03-09 미래 이벤트를 만들었다. 문장 경계로 끊어야 막힌다.
    {'nid': 'B4', 'title': '에프에스티, 자사주 51만주 소각 결정',
     'body': ('에프에스티는 10일 보통주 51만주를 소각하기로 결정했다고 공시했다. '
              '소각 예정일은 3월20일이다. 소각 예정 금액은 178억5000만원이다. '
              '이는 3월9일 종가 3만5000원을 기준으로 산출한 금액이다. '
              '이번 소각은 기취득 자기주식을 활용한...'),
     'datetime': '2026-03-10T14:41:00+09:00', 'relevant': True},
]
eq(tac.news_calendar_items(real_bugs, TODAY), [],
   '실측 오탐 4건(집계기사/등락보도/발행일 자기언급/문장 넘은 맥락어) 모두 제외')

# 미래 의도 맥락어가 날짜 앞뒤 25자 안에 없으면 제외 (날짜만 있고 예정/개최 등 단어가 없다)
no_context = [{'nid': 'NC', 'title': '탐방 후기, 회사는 11월 5일 즈음 담당자와 통화했다고 밝혔다',
               'body': '', 'datetime': '2026-08-01T09:00:00+09:00', 'relevant': True}]
eq(tac.news_calendar_items(no_context, TODAY), [], '미래 의도 단어 없는 날짜 언급은 제외')

# ---------- 요구사항 6번 예시: "소각 예정일은 3월20일" (발행 2026-03-10) ----------
cancel_news = [{'nid': 'NX', 'title': '에프에스티, 자사주 소각 계획 공개',
                'body': '소각 예정일은 3월20일이다.',
                'datetime': '2026-03-10T09:00:00+09:00', 'relevant': True}]
kept = tac.news_calendar_items(cancel_news, date(2026, 3, 12))
eq(len(kept), 1, 'today=2026-03-12 -- 3/20 은 아직 미래라 유지')
eq(kept[0]['date'], date(2026, 3, 20), '무연도 "3월20일" -> 발행연도(2026) 로 추론')
excluded = tac.news_calendar_items(cancel_news, date(2026, 9, 17))
eq(excluded, [], 'today=2026-09-17 -- 3/20 은 이미 지났으므로 제외')

# today 이전 날짜(연도 명시)는 news_calendar_items 자체에서 제외된다
news_past = {'items': [
    {'nid': 'N2', 'title': '2026년 1월 15일 실적 발표 예정 안내 회고', 'body': '',
     'datetime': '2025-12-01T09:00:00+09:00', 'relevant': True},
    {'nid': 'N4', 'title': '2027년 3월 2일 증설 목표로 공장 착공', 'body': '',
     'datetime': '2026-06-01T09:00:00+09:00', 'relevant': True},
]}
past_payload = tac.build_calendar('테스트종목', TODAY, horizon_days=270,
                                   filings=None, news=news_past, settle_month='6월')
news_out = [it for it in past_payload['items'] if it['basis'] == '뉴스']
eq(len(news_out), 1, '과거 연도 날짜(2026-01-15)는 today 이전이라 제외되고 미래(2027-03-02)만 남는다')

# ---------- 6. build_calendar: 병합 + 정렬 + horizon/오늘 필터 ----------
# IR 전년패턴용: 2025-10-05(일) + 1년 = 2026-10-05(월, today 이후) -- 평일이라 보정 없음
filings_full = {
    'list': [{'date': '20251005', 'name': '기업설명회(IR)개최(안내공시)', 'rcept_no': 'R1'}],
    'bodies': disp_bodies + ir_bodies,  # 자기주식 2건(9/20,9/25) + IR 1건(11/5, IR body M2)
}
news_full = {'items': news_items}
payload = tac.build_calendar('테스트종목', TODAY, horizon_days=270,
                              filings=filings_full, news=news_full, settle_month=None)
eq(payload['stock'], '테스트종목', 'stock 필드')
eq(payload['today'], '2026-09-17', 'today ISO 문자열')
result_dates = [it['date'] for it in payload['items']]
eq(result_dates, sorted(result_dates), '날짜 오름차순 정렬')
cids = [it['cid'] for it in payload['items']]
eq(cids, [f'C{i:02d}' for i in range(1, len(cids) + 1)], 'cid 는 C01 부터 순번')
eq(all(len(it['sources']) >= 0 for it in payload['items']), True, '모든 항목에 sources 배열 존재')
# IR 이벤트가 전년패턴(list)과 공시(bodies, M2)에서 각각 나오지만 이름이 달라 병합되지 않는다
eq(sum(1 for it in payload['items'] if it['basis'] == '공시' and it['event'] == '기업설명회(IR) 개최'), 1,
   '공시 basis 의 IR 개최 1건')
eq(sum(1 for it in payload['items'] if it['basis'] == '전년패턴'), 1, '전년패턴 basis 1건(주말 보정된 9/7)')

# 병합: 같은 날짜 + 같은 이벤트명을 가진 두 소스가 있으면 sources 가 합쳐진다
dup_bodies = [
    {'name': '주요사항보고서(자기주식처분결정)', 'rcept_no': 'X1',
     'text': '처분예정기간\n 시작일\n2026년 09월 20일\n\n 종료일\n2026년 09월 20일'},
    {'name': '[기재정정]주요사항보고서(자기주식처분결정)', 'rcept_no': 'X2',
     'text': '처분예정기간\n 시작일\n2026년 09월 20일\n\n 종료일\n2026년 09월 20일'},
]
dup_payload = tac.build_calendar('테스트종목', TODAY, horizon_days=270,
                                  filings={'list': [], 'bodies': dup_bodies}, news=None, settle_month=None)
start_items = [it for it in dup_payload['items'] if it['event'] == '자기주식 처분 시작']
eq(len(start_items), 1, '같은 날짜·같은 이벤트는 하나로 병합')
eq(len(start_items[0]['sources']), 2, '병합된 항목의 sources 는 두 출처를 모두 담는다')

# news.json 없음 -> 뉴스 규칙 건너뜀, filings 없음 -> 전년패턴/공시 건너뜀
none_payload = tac.build_calendar('테스트종목', TODAY, horizon_days=270, filings=None, news=None, settle_month=None)
skip_rules = {s['rule'] for s in none_payload['skipped']}
eq(skip_rules, {'전년패턴', '공시', '뉴스'}, 'filings/news 모두 없으면 세 규칙을 건너뛰고 사유를 남긴다')
eq(any(it['basis'] == '법정기한' for it in none_payload['items']), True, '법정기한 규칙은 filings 없어도 동작')

# 결산월이 12월이 아니면 법정기한 항목이 아예 없고 skipped 에 사유가 남는다
fy_payload = tac.build_calendar('테스트종목', TODAY, horizon_days=270, filings=None, news=None,
                                 settle_month='6월')
eq(any(it['basis'] == '법정기한' for it in fy_payload['items']), False, '결산월 6월이면 법정기한 항목 없음')
eq(any(s['rule'] == '법정기한' for s in fy_payload['skipped']), True, '법정기한 skip 사유 기록')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_calendar 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
