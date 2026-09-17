"""ta_dart_diff.py 테스트 (Task 7).

DART 정기보고서 전문을 장 단위 파일로 쪼개고, 직전 보고서 대비 바뀐 문단만
뽑는다. 네트워크 없음 -- 전부 합성 텍스트 + tempdir.

실행: python tests/test_ta_dart_diff.py
"""
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_common as tc                                  # noqa: E402
import ta_dart_diff as td                                # noqa: E402

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


# ==================== parse_filename / find_reports (기간 정렬) ====================
eq(td.parse_filename('_dart_FULL_사업보고서(2025.12)_20260318001663.txt'),
   {'type': '사업보고서', 'period': '2025.12', 'rcept': '20260318001663'},
   'parse_filename 은 type/period/rcept 를 뽑는다')
eq(td.parse_filename('아무거나.txt'), None, '패턴 불일치는 None')

with tempfile.TemporaryDirectory() as td_dir:
    # 일부러 뒤섞어서 만든다 -- 기간순 정렬이 파일시스템 순서에 의존하면 안 된다
    for fn in ['_dart_FULL_반기보고서(2026.06)_20260814001563.txt',
               '_dart_FULL_사업보고서(2025.12)_20260318001663.txt',
               '_dart_FULL_분기보고서(2026.03)_20260514000167.txt']:
        with open(os.path.join(td_dir, fn), 'w', encoding='utf-8') as f:
            f.write('x')
    reports = td.find_reports(td_dir)
    eq([r['period'] for r in reports], ['2025.12', '2026.03', '2026.06'],
       '기간 정렬(2025.12 < 2026.03 < 2026.06)')
    eq(td.find_reports(os.path.join(td_dir, '없음')), [], '없는 폴더는 빈 목록')

# ==================== get_chapters -- TOC 구간 중복 대장 제목은 본문 쪽 ====================
TOC_DOC = """\
목차

I. 회사의 개요
II. 사업의 내용
III. 재무에 관한 사항

I. 회사의 개요
1. 회사의 개요
당사는 반도체 장비 부품 회사이다.

II. 사업의 내용
1. 사업의 개요
당사는 펠리클을 생산한다.

III. 재무에 관한 사항
1. 요약재무정보
자산총계는 500억원이다.
"""
toc_lines = TOC_DOC.splitlines(keepends=True)
chapters = td.get_chapters(toc_lines)
titles = [c['title'] for c in chapters]
eq(titles, ['I. 회사의 개요', 'II. 사업의 내용', 'III. 재무에 관한 사항'],
   '대장 제목은 중복 제거 후 3개만 남는다')
i_chap = next(c for c in chapters if c['title'] == 'I. 회사의 개요')
eq(i_chap['start'], 7, 'I 는 목차(3행)가 아니라 본문(7행) 쪽을 쓴다')
ii_chap = next(c for c in chapters if c['title'] == 'II. 사업의 내용')
eq(ii_chap['start'], 11, 'II 도 본문 쪽 줄번호')
eq(ii_chap['end'], 14, 'II 의 끝은 III 시작 줄(15) 바로 전')

# ==================== get_subsections -- 소장 경계 ====================
SUB_DOC = """\
II. 사업의 내용
1. 사업의 개요
개요 문단.

2. 주요 제품 및 서비스
제품 설명 문단.

3. 원재료 및 생산설비
설비 문단.
"""
sub_lines = SUB_DOC.splitlines(keepends=True)
subs = td.get_subsections(sub_lines, 1, len(sub_lines))
eq([s['title'] for s in subs], ['1. 사업의 개요', '2. 주요 제품 및 서비스', '3. 원재료 및 생산설비'],
   '소장 3개 순서대로')
eq(subs[0]['start'], 2, '1번 소장 시작줄')
eq(subs[0]['end'], 4, '1번 소장 끝은 2번 시작 전')
eq(subs[2]['end'], len(sub_lines), '마지막 소장은 범위 끝까지')

# ==================== get_subsections -- 소장 오탐 방지 (fix round 2) ====================
# round 1(직전 번호+1 만 허용)은 각주 오탐은 잡았지만, 진짜 스킵(24->26)이 있는
# 실제 문서에서 그 뒤 소장(우발상황과 약정사항/특수관계자 거래)까지 통째로 날려버렸다.
# round 2 세 조건 -- 하나라도 어기면 본문:
#   (a) 번호가 직전 인정 번호보다 크고 차이가 3 이하, 또는 번호가 1~3(중첩 재시작 허용)
#   (b) 번호 뒤 제목이 60자 이하
#   (c) 제목이 "...니다.", "...참조", "...바랍니다" 처럼 문장으로 안 끝나고
#       "참조하시기"/"바랍니다"/"기재하였습니다" 를 포함하지 않는다

# (b) 길이 조건만으로 걸러지는 경우 -- 번호는 기대값(2)과 정확히 일치하고 문장 끝맺음도
# 아니지만(조건 c 무관) 60자를 넘는 제목
LONG_HEADING_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
내용.

2. 가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하가나다라마바사아자차카타파하
정상 문장.
"""
long_lines = LONG_HEADING_DOC.splitlines(keepends=True)
long_subs = td.get_subsections(long_lines, 1, len(long_lines))
eq([s['title'] for s in long_subs], ['1. 요약재무정보'],
   '60자 넘는 제목은 번호가 맞아도 소장이 되지 않는다 (조건 b)')

# (c) 문장 끝맺음 조건만으로 걸러지는 경우 -- 번호는 기대값(3)이고 60자 이내지만 "...바랍니다"
SENTENCE_ENDING_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
내용.

2. 연결재무제표
내용.

3. 자세한 내용은 첨부자료를 참조하시기 바랍니다
정상 문장.
"""
sentence_lines = SENTENCE_ENDING_DOC.splitlines(keepends=True)
sentence_subs = td.get_subsections(sentence_lines, 1, len(sentence_lines))
eq([s['title'] for s in sentence_subs], ['1. 요약재무정보', '2. 연결재무제표'],
   '번호/길이가 다 맞아도 문장으로 끝나면(참조하시기/바랍니다) 소장이 되지 않는다 (조건 c)')

# (a) 순서 조건만으로 걸러지는 경우 -- 제목은 짧고 문장도 아니지만 간격이 3 초과(1 다음 5)
BAD_SEQUENCE_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
내용.

5. 특수관계자 거래
내용.
"""
seq_lines = BAD_SEQUENCE_DOC.splitlines(keepends=True)
seq_subs = td.get_subsections(seq_lines, 1, len(seq_lines))
eq([s['title'] for s in seq_subs], ['1. 요약재무정보'],
   '간격이 3을 넘게 건너뛰면(1->5) 리셋 번호(1~3)가 아닌 한 소장이 되지 않는다 (조건 a)')

# (a) 거꾸로 -- 직전보다 작은(그리고 리셋 범위 1~3 밖인) 번호도 순서 위반으로 거절
OUT_OF_ORDER_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
내용.

2. 연결재무제표
내용.

3. 연결재무제표 주석
내용.

6. 사채
내용.

4. 차입금
내용.
"""
ooo_lines = OUT_OF_ORDER_DOC.splitlines(keepends=True)
ooo_subs = td.get_subsections(ooo_lines, 1, len(ooo_lines))
eq([s['title'] for s in ooo_subs],
   ['1. 요약재무정보', '2. 연결재무제표', '3. 연결재무제표 주석', '6. 사채'],
   '직전(6)보다 작고 리셋 범위(1~3) 밖인 번호(4)는 순서 위반(out-of-order)으로 소장이 되지 않는다')

# 진짜 스킵(간격 <=3)은 이제 유지된다 -- round 1 트레이드오프를 뒤집은 핵심 케이스
GENUINE_SKIP_DOC = """\
III. 재무에 관한 사항
1. 일반사항 (연결)
내용.

2. 영업부문 정보 (연결)
내용.

4. 특수관계자 거래 (연결)
내용.
"""
skip_lines = GENUINE_SKIP_DOC.splitlines(keepends=True)
skip_subs = td.get_subsections(skip_lines, 1, len(skip_lines))
eq([s['title'] for s in skip_subs],
   ['1. 일반사항 (연결)', '2. 영업부문 정보 (연결)', '4. 특수관계자 거래 (연결)'],
   '3번이 빠지고 바로 4번이 와도(간격 2, 실제 스킵) 4번은 소장으로 인정된다 (round 2)')

# 실측 재현 -- 에프에스티 24->26 스킵처럼 간격 3 이내 스킵이 있어도 그 뒤 키워드 소장은
# 살아남고, 진짜 각주 문장(번호도 멀고 문장으로도 끝남)만 걸러진다
JUNK_MID_BODY_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
내용.

1. 일반사항 (연결)
일반사항 내용.

2. 영업부문 정보 (연결)
반도체 부문 매출은 80억원이다.

3. 차입금 (연결)
차입금 잔액은 50억원이다.

6. 우발상황과 약정사항 (연결)
우발상황은 없다.

7. 특수관계자 거래 (연결)
특수관계자 거래는 없다.

34. 우발상황과 약정사항 내용을 참조하시기 바랍니다.(4) 기타 재무제표 이용에 유의하여야 할 사항이 있으니 확인이 필요합니다- 해당사항 없음
정상적인 본문 문장이 이어진다.
"""
junk_lines = JUNK_MID_BODY_DOC.splitlines(keepends=True)
junk_subs = td.get_subsections(junk_lines, 1, len(junk_lines))
junk_titles = [s['title'] for s in junk_subs]
eq(any(t.startswith('34.') for t in junk_titles), False,
   '실측 재현: "34. 우발상황과 약정사항 내용을 참조..." 각주 문장은 소장이 되지 않는다')
junk_struct = td.build_ta_sections(junk_lines)
note_titles_junk = [n['title'] for n in junk_struct['notes']]
eq(any(t.startswith('34.') for t in note_titles_junk), False,
   'notes_selected 에도 이 각주 문장이 섞이지 않는다')
eq(sorted(note_titles_junk),
   sorted(['2. 영업부문 정보 (연결)', '3. 차입금 (연결)',
           '6. 우발상황과 약정사항 (연결)', '7. 특수관계자 거래 (연결)']),
   '4->6 스킵(간격 2)을 넘어서도 진짜 키워드 소장 4개는 전부 살아남는다')

# 순서대로(스킵 없이)면 여전히 정상 동작 -- 회귀 확인
SEQUENTIAL_OK_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
내용.

1. 일반사항 (연결)
내용.

2. 영업부문 정보 (연결)
내용.

3. 차입금 (연결)
내용.

4. 사채 (연결)
내용.
"""
ok_lines = SEQUENTIAL_OK_DOC.splitlines(keepends=True)
ok_subs = td.get_subsections(ok_lines, 1, len(ok_lines))
eq([s['title'] for s in ok_subs],
   ['1. 요약재무정보', '1. 일반사항 (연결)', '2. 영업부문 정보 (연결)',
    '3. 차입금 (연결)', '4. 사채 (연결)'],
   '진짜 소장이 스킵 없이 순서대로면 전부 인정된다 (회귀 없음)')

# ==================== slice_lines + format_numbered_file -- 원본 줄번호 접두 ====================
sliced = td.slice_lines(sub_lines, 2, 3)
eq(sliced, [(2, '1. 사업의 개요'), (3, '개요 문단.')], 'slice_lines 는 (원본줄번호, 텍스트) 쌍')
body, start, end = td.format_numbered_file('원본.txt', sliced)
eq(body.splitlines()[0], '# source: 원본.txt lines 2-3', '첫 줄은 source 헤더')
eq(body.splitlines()[1], '2\t1. 사업의 개요', '각 줄 앞에 원본줄번호 탭 접두')
eq((start, end), (2, 3), 'start/end 는 실제 포함된 줄번호')

# ==================== build_ta_sections -- notes_selected 제목 필터 ====================
NOTES_DOC = """\
III. 재무에 관한 사항
1. 요약재무정보
자산총계는 500억원이다.

1. 일반사항 (연결)
일반사항 내용.

2. 영업부문 정보 (연결)
반도체 부문 매출은 80억원이다.

3. 차입금 (연결)
차입금 잔액은 50억원이다.

4. 특수관계자 거래 (연결)
특수관계자 거래는 없다.
"""
notes_lines = NOTES_DOC.splitlines(keepends=True)
struct = td.build_ta_sections(notes_lines)
note_titles = [n['title'] for n in struct['notes']]
eq(sorted(note_titles),
   sorted(['2. 영업부문 정보 (연결)', '3. 차입금 (연결)', '4. 특수관계자 거래 (연결)']),
   'notes_selected 는 키워드 포함 소장만 (요약재무정보/일반사항 제외)')

# ==================== diff_paragraphs -- added/removed/numbers_only/table (fix round 3) ====================
prev_paras = td.split_paragraphs([(10, '매출액은 100억원이다.')])
latest_paras_num = td.split_paragraphs([(10, '매출액은 120억원이다.')])
changes = td.diff_paragraphs('II-4 매출 및 수주상황', prev_paras, latest_paras_num)
eq(len(changes), 1, '숫자만 바뀐 문단은 removed+added 2건이 아니라 합쳐진 1건')
eq(changes[0]['kind'], 'numbers_only', '숫자만 바뀌면 kind=numbers_only')
eq(changes[0]['change'], 'changed', '합쳐진 레코드는 change=changed')
eq(changes[0]['line'], 10, '합쳐진 레코드의 line 은 latest(added) 쪽 줄번호')
eq(changes[0]['prev_line'], 10, 'prev_line 은 previous(removed) 쪽 줄번호도 보존한다')

prev_paras2 = td.split_paragraphs([(20, '주요 제품은 펠리클이다.')])
latest_paras_text = td.split_paragraphs([(20, '주요 제품은 펠리클과 오링이다.')])
changes2 = td.diff_paragraphs('II-2 주요 제품 및 서비스', prev_paras2, latest_paras_text)
eq(set(c['kind'] for c in changes2), {'text'}, '텍스트 자체가 바뀌면 kind=text')
eq([c['change'] for c in changes2], ['modified'], '비슷한 문단은 removed+added 가 아니라 modified 1건 (round 4)')
eq((changes2[0]['before'], changes2[0]['after']), ('주요 제품은 펠리클이다.', '주요 제품은 펠리클과 오링이다.'),
   'modified 는 before/after 를 함께 담는다')

same_paras = td.split_paragraphs([(30, '변화 없음.')])
eq(td.diff_paragraphs('X', same_paras, same_paras), [], '동일 문단은 변경 없음')

only_latest = td.split_paragraphs([(40, '새로 추가된 문단.')])
changes3 = td.diff_paragraphs('X', [], only_latest)
eq(len(changes3), 1, '이전에 없던 문단은 added 1건')
eq(changes3[0]['change'], 'added', 'add-only 는 added')
eq(changes3[0]['line'], 40, 'added 는 latest 의 원본 줄번호를 쓴다')

# ==================== fix round 3 -- classify_kind (실측 샘플) ====================
# 컨트롤러가 짚은 실측 샘플: 표 행이 kind=text 로 새서 노이즈가 됐다.
eq(td.classify_kind('재료 계 - 104,756(65.94%)'), 'table',
   '실측 샘플 1: 표 행(수치+퍼센트)은 table')
eq(td.classify_kind('매출액 합계 - 158,858(100%)'), 'table',
   '실측 샘플 2: 표 행(수치+퍼센트)은 table')
eq(td.classify_kind('품 목 분 류 제40기 반기 제39기 제38기'), 'table',
   '실측 샘플 3: 숫자 토큰 비율은 낮아도 기간 라벨을 지우면 12자 미만만 남아 table')
eq(td.classify_kind('당사는 반도체 부품을 생산한다.'), 'text', '평범한 산문은 여전히 text (회귀 확인)')
eq(td.classify_kind('특이사항 없음.'), 'text',
   '판단: 숫자/기간 라벨이 아예 없는 짧은 문장은 12자 미만이어도 table 로 보지 않는다 '
   '(지운 게 없는데 짧다고 표로 보면 진짜 산문까지 오탐)')

# ==================== fix round 3 -- numbers_only 는 쌍 전체에서 결정 (조건 1) ====================
# "재료 계 -" 처럼 opcode 가 replace 로 깔끔하게 짝짓지 못하는 경우(사이에 동일 문단이
# 끼어 delete+insert 로 갈리는 경우)에도 numbers_only 매칭이 되는지 확인한다.
prev_cross = td.split_paragraphs([
    (10, '매출액은 100억원이다.'),
    (11, ''),
    (12, '공통 문장.'),
])
latest_cross = td.split_paragraphs([
    (10, '공통 문장.'),
    (11, ''),
    (13, '매출액은 120억원이다.'),
])
cross_changes = td.diff_paragraphs('X', prev_cross, latest_cross)
eq(len(cross_changes), 1,
   '동일 문단이 사이에 끼어 delete+insert 로 갈려도(같은 index 짝이 아니어도) '
   '숫자만 다른 문단은 여전히 하나의 numbers_only 로 묶인다')
eq(cross_changes[0]['kind'], 'numbers_only', '쌍 전체 검색으로 찾은 매칭도 kind=numbers_only')

# 표 행끼리도 숫자만 다르면 numbers_only 가 table 분류보다 우선한다
prev_table_num = td.split_paragraphs([(50, '재료 계 - 104,756(65.94%)')])
latest_table_num = td.split_paragraphs([(50, '재료 계 - 97,123(61.20%)')])
table_num_changes = td.diff_paragraphs('III 주석 3. 영업부문 정보', prev_table_num, latest_table_num)
eq(len(table_num_changes), 1, '표 행이라도 숫자만 다르면 numbers_only 1건으로 합쳐진다')
eq(table_num_changes[0]['kind'], 'numbers_only', 'numbers_only 매칭이 table 분류보다 먼저 적용된다')

# 표 행이 구조적으로 달라지면(숫자만의 차이가 아니면) numbers_only 매칭이 안 되고
# 남은 문단은 각각 kind=table 로 분류된다 (조건 2)
prev_table_diff = td.split_paragraphs([(60, '재료 계 - 104,756(65.94%)')])
latest_table_diff = td.split_paragraphs([(60, '부재료 계 - 12,000(7.5%)')])
table_diff_changes = td.diff_paragraphs('III 주석 3. 영업부문 정보', prev_table_diff, latest_table_diff)
eq(len(table_diff_changes), 2, '구조가 다른 표 행은 매칭되지 않고 removed+added 2건')
eq(set(c['kind'] for c in table_diff_changes), {'table'}, '매칭 안 된 표 행은 각각 kind=table')

# ==================== fix round 3 -- 소장 tail 컷 (조건 3) ====================
# "4. 재무제표" 처럼 그 자체는 round 2 규칙(간격<=3, 리셋 1~3)에 걸려 소장으로
# 인정되지 않아도, 직전 소장은 거기서 끊겨야 한다. 실측: "6. 특수관계자 거래" 뒤에
# 번호가 다시 작아지는 "4. 재무제표" 가 오면, round 2 까지는 다음 인정 소장(리셋된
# "1. 일반사항")까지 전부 흡수해 range 가 실제보다 훨씬 길어졌다.
TAIL_STOP_DOC = """\
III. 재무에 관한 사항
1. 일반사항 (연결)
내용1.

2. 영업부문 정보 (연결)
내용2.

3. 차입금 (연결)
내용3.

6. 특수관계자 거래 (연결)
내용6-1.
내용6-2.

4. 재무제표
비연결 재무제표 내용 시작.
꼬리 문장.

1. 일반사항
내용.
"""
tail_lines = TAIL_STOP_DOC.splitlines(keepends=True)
tail_subs = td.get_subsections(tail_lines, 1, len(tail_lines))
tail6 = next(s for s in tail_subs if s['title'] == '6. 특수관계자 거래 (연결)')
tail_stop_line = next(i for i, l in enumerate(tail_lines, 1) if l.startswith('4. 재무제표'))
eq(tail6['end'] < tail_stop_line, True,
   '"6. 특수관계자 거래"는 (인정되지 않는) "4. 재무제표" 줄 이전에서 끊긴다')
tail_struct = td.build_ta_sections(tail_lines)
tail_note = next(n for n in tail_struct['notes'] if n['title'] == '6. 특수관계자 거래 (연결)')
tail_text = ' '.join(t for _, t in tail_note['content'])
eq('재무제표' in tail_text, False, 'notes_selected 로 뽑힌 소장 본문에 다음 장 표제가 안 섞인다')
eq('꼬리 문장' in tail_text, False, '그 표제 뒤 내용도 같이 안 섞인다')

# ==================== fix round 4 -- 비슷한 산문 짝짓기 (modified) ====================
# 에프에스티 실측: CO2 Chiller 가 "시제품 개발 및 평가 진행 중" -> "고객사 납품 완료" 로 바뀐 신호가
# removed + added 두 건으로 흩어져 있었다.
co2_prev = td.split_paragraphs([(1735, '친환경 냉매 칠러 개발" - 에너지 절감형 CO2 Chiller 시제품 개발 및 국내외 고객사 평가 진행 중')])
co2_latest = td.split_paragraphs([(2558, '친환경 냉매 칠러 개발" - 제어 정밀도 및 온도 안정성 검증 진행 중- 에너지 절감형 CO2 Chiller 고객사 납품 완료 및 평가 진행 중')])
co2 = td.diff_paragraphs('II-6 주요계약 및 연구개발활동', co2_prev, co2_latest)
eq([c['change'] for c in co2], ['modified'], 'CO2 Chiller 실측 문단은 modified 1건으로 짝지어진다')
eq((co2[0]['line_before'], co2[0]['line']), (1735, 2558), 'modified 는 양쪽 원본 줄번호를 보존')
eq(co2[0]['similarity'] >= 0.6, True, 'similarity 가 기록되고 임계값 이상')
eq('납품 완료' in co2[0]['after'] and '시제품' in co2[0]['before'], True, 'before/after 원문 앞부분')

unrel = td.diff_paragraphs('X', td.split_paragraphs([(1, '당사는 신규 공장 부지를 매입하였습니다.')]),
                           td.split_paragraphs([(2, '대표이사가 변경되어 이사회 구성이 달라졌습니다.')]))
eq(sorted(c['change'] for c in unrel), ['added', 'removed'], '안 닮은 문단은 짝짓지 않는다')

# fix round 5 -- 임계값 0.55
eq(td._PAIR_MIN, 0.55, '짝짓기 임계값은 0.55')
eq(co2[0]['similarity'] >= 0.55, True, 'CO2 Chiller 실측 짝은 0.55 에서도 유지')

# fix round 5 -- 그림 캡션(파일명)은 table, highlights 제외
eq(td.classify_kind('시스템반도체 시장규모 전망.jpg 시스템반도체 시장규모 전망'), 'table', '실측 캡션 "파일명.jpg 파일명" 은 table')
eq(td.classify_kind('비메모리반도체 시장추이 및 전망(260630).JPEG'), 'table', '.jpeg 로 끝나면 table (대소문자 무관)')
eq(td.classify_kind('chart.gif'), 'table', '.gif 파일명뿐이면 table')
eq(td.classify_kind('자세한 내용은 그림.png 파일을 참고하시기 바랍니다.'), 'text', '문장 안에 파일명이 섞인 산문은 text 유지')
img = td.diff_paragraphs('II-7 기타 참고사항',
                         td.split_paragraphs([(2650, '시스템반도체 시장규모 전망.jpg 시스템반도체 시장규모 전망')]),
                         td.split_paragraphs([(2650, '비메모리반도체 시장추이 및 전망(260630).jpg 비메모리반도체 시장추이 및 전망(260630)')]))
eq(sorted((c['kind'], c['change']) for c in img), [('table', 'added'), ('table', 'removed')], '캡션 변경은 modified 로 짝짓지 않고 table')
eq(td.build_highlights(img, None), [], '캡션 변경은 highlights 에 안 들어간다')

# 1:1 greedy -- 더 닮은 쪽이 먼저 짝을 가져간다
g_prev = td.split_paragraphs([(1, '펠리클 매출이 고객사 증설로 크게 늘었습니다.'), (3, '다른 이야기 전혀 무관한 문장입니다.')])
g_latest = td.split_paragraphs([(1, '펠리클 매출이 고객사 증설로 크게 늘었습니다 다만.'),
                               (3, '펠리클 매출이 고객사 증설로 늘었습니다.')])
g = td.diff_paragraphs('X', g_prev, g_latest)
g_mod = [c for c in g if c['change'] == 'modified']
eq(len(g_mod), 1, '하나의 removed 는 하나의 added 와만 짝지어진다')
eq(g_mod[0]['line'], 1, 'greedy best-first -- 가장 닮은 added 가 짝이 된다')

# ==================== fix round 4 -- 기간 단어 정규화 ====================
eq(td._digit_period_norm('당분기말로부터 잔존기간에 따른 만기일로 구분'),
   td._digit_period_norm('당반기로부터 잔존기간에 따른 만기일로 구분'), '당분기말/당반기 는 같은 @')
per = td.diff_paragraphs('II-5 위험관리 및 파생거래',
                         td.split_paragraphs([(1499, '연결회사의 금융부채를 당분기말로부터 계약 만기일까지의 잔여기간에 따라 만기일로 구분한 내역은 다음과 같습니다.')]),
                         td.split_paragraphs([(2322, '연결회사의 금융부채를 당반기로부터 계약 만기일까지의 잔여기간에 따라 만기일로 구분한 내역은 다음과 같습니다.')]))
eq([(c['kind'], c['change']) for c in per], [('numbers_only', 'changed')], '기간 단어만 다르면 numbers_only')
eq(td._digit_period_norm('전기말 대비 당기말 증가'), '@ 대비 @ 증가', '전기말/당기말 도 @')

# ==================== fix round 4 -- highlights ====================
hl_changes = [
    {'section': 'III 주석 3. 영업부문 정보', 'kind': 'text', 'change': 'added', 'text': '부문 구성이 바뀌었습니다.', 'line': 1},
    {'section': 'III 주석 34. 우발상황과 약정사항', 'kind': 'text', 'change': 'added', 'text': '신규 소송이 제기되었습니다.', 'line': 2},
    {'section': 'II-6 주요계약 및 연구개발활동', 'kind': 'text', 'change': 'added', 'text': 'CO2 Chiller 고객사 납품 완료.', 'line': 3},
    {'section': 'II-6 주요계약 및 연구개발활동', 'kind': 'text', 'change': 'modified', 'before': 'a', 'after': '시제품 평가 완료.', 'line': 4, 'line_before': 1},
    {'section': 'II-2 주요 제품 및 서비스', 'kind': 'text', 'change': 'added', 'text': '당사는 반도체 부품을 생산합니다.', 'line': 5},
    {'section': 'II-4 매출 및 수주상황', 'kind': 'table', 'change': 'added', 'text': '재료 계 - 1', 'line': 6},
    {'section': 'II-4 매출 및 수주상황', 'kind': 'text', 'change': 'removed', 'text': '삭제된 문장입니다.', 'line': 7},
]
hl_prev = {'business': {'content': [(9, '1. 사업의 개요'), (10, '당사는 반도체 부품을 생산합니다. 다른 문장.')]},
           'notes': [], 'IV': None, 'VII': None}
hl = td.build_highlights(hl_changes, hl_prev)
eq([h['line'] for h in hl], [4, 3, 2, 1],
   '본문 장(modified 먼저) > 핵심 주석 > 기타 주석, 보일러플레이트/table/removed 제외')
eq(len(td.build_highlights(hl_changes * 10, None)) <= 30, True, 'highlights 는 최대 30건')

# ==================== run() 통합 -- 파일 3편, 최신/직전 선택 + 산출물 ====================
PREV_FULL = """\
반기보고서

II. 사업의 내용
1. 사업의 개요
당사는 반도체 부품을 생산한다.

2. 주요 제품 및 서비스
주요 제품은 펠리클이다.

3. 원재료 및 생산설비
원재료는 폴리이미드이다.

4. 매출 및 수주상황
매출액은 100억원이다.

5. 위험관리 및 파생거래
환율 변동에 따른 위험이 있다.

6. 주요계약 및 연구개발활동
연구개발비는 10억원이다.

7. 기타 참고사항
특이사항 없음.

III. 재무에 관한 사항
1. 요약재무정보
자산총계는 500억원이다.

1. 일반사항 (연결)
일반사항 내용.

2. 영업부문 정보 (연결)
반도체 부문 매출은 80억원이다.

3. 차입금 (연결)
차입금 잔액은 50억원이다.

4. 특수관계자 거래 (연결)
특수관계자 거래는 없다.

IV. 이사의 경영진단 및 분석의견
전반적으로 안정적인 실적을 유지하고 있다.

VII. 주주에 관한 사항
최대주주는 홍길동이다.
"""

LATEST_FULL = PREV_FULL \
    .replace('매출액은 100억원이다.', '매출액은 120억원이다.') \
    .replace('주요 제품은 펠리클이다.', '주요 제품은 펠리클과 오링이다.') \
    .replace('차입금 잔액은 50억원이다.', '차입금 잔액은 45억원이다.') \
    .replace('전반적으로 안정적인 실적을 유지하고 있다.', '수요 둔화로 실적이 악화되었다.')

with tempfile.TemporaryDirectory() as root:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = root
    try:
        data_d = tc.data_dir('테스트종목')
        os.makedirs(data_d, exist_ok=True)
        with open(os.path.join(data_d, '_dart_FULL_사업보고서(2025.12)_20260318000001.txt'),
                  'w', encoding='utf-8') as f:
            f.write(PREV_FULL)
        with open(os.path.join(data_d, '_dart_FULL_반기보고서(2026.03)_20260318000002.txt'),
                  'w', encoding='utf-8') as f:
            f.write(PREV_FULL)  # 중간 기간 -- 최신/직전 선택에서 제외돼야 함
        with open(os.path.join(data_d, '_dart_FULL_반기보고서(2026.06)_20260318000003.txt'),
                  'w', encoding='utf-8') as f:
            f.write(LATEST_FULL)

        result = td.run('테스트종목')

        eq(result['status'], 'ok', '3편 존재 -> ok')
        eq(result['latest']['period'], '2026.06', '최신은 가장 나중 기간')
        eq(result['previous']['period'], '2026.03', '직전은 그 바로 전 기간 (2025.12 아님)')

        names = sorted(f['name'] for f in result['files'])
        eq(names, ['business.txt', 'mdna.txt', 'notes_selected.txt',
                    'risk_mgmt.txt', 'shareholders.txt'],
           '산출 파일 5종')

        biz = next(f for f in result['files'] if f['name'] == 'business.txt')
        eq(biz['source_lines'][0], 3, 'business.txt 는 latest 의 II 시작줄부터')

        dart_out = os.path.join(tc.ta_dir('테스트종목'), 'dart')
        with open(os.path.join(dart_out, 'business.txt'), encoding='utf-8') as f:
            biz_text = f.read()
        eq(biz_text.splitlines()[0].startswith('# source:'), True,
           'business.txt 첫 줄은 source 헤더')
        eq('펠리클과 오링' in biz_text, True, 'business.txt 는 latest 본문을 담는다')

        with open(os.path.join(dart_out, 'notes_selected.txt'), encoding='utf-8') as f:
            notes_text = f.read()
        eq('영업부문' in notes_text and '차입금' in notes_text and '특수관계자' in notes_text,
           True, 'notes_selected.txt 는 키워드 소장을 담는다')
        eq('요약재무정보' in notes_text, False, '요약재무정보는 키워드가 아니라 빠진다')

        sections = set(c['section'] for c in result['changes'])
        eq(any(s.startswith('II-4') for s in sections), True, 'II-4 매출 변경 포함')
        eq(any(s.startswith('II-2') for s in sections), True, 'II-2 제품 변경 포함')
        eq(any('차입금' in s for s in sections), True, '차입금 소장 변경 포함')
        eq(any(s.startswith('IV') for s in sections), True, 'IV 변경 포함')
        eq(any(s.startswith('VII') for s in sections), False, 'VII 은 안 바뀌어서 빠진다')

        num_kinds = [c['kind'] for c in result['changes'] if c['section'].startswith('II-4')]
        eq(set(num_kinds), {'numbers_only'}, 'II-4 매출 변경은 numbers_only')
        text_kinds = [c['kind'] for c in result['changes'] if c['section'].startswith('II-2')]
        eq(set(text_kinds), {'text'}, 'II-2 제품 변경은 text')

        eq(result['summary']['numbers_only'] >= 2, True,
           'summary.numbers_only 는 매출/차입금 2건 이상 (쌍 합산 후 레코드 수)')
        eq(result['summary']['text_modified'] >= 1, True,
           'summary.text_modified 는 제품 문단 1건 이상 (round 4 -- 짝지어진 산문)')
        eq(result['summary']['text_added'] + result['summary']['text_modified'] >= 2, True,
           'summary 의 산문 변경(added+modified)은 제품/IV 2건 이상')
        hl_secs = [h['section'] for h in result['highlights']]
        eq(any(s.startswith('II-2') for s in hl_secs), True, 'highlights 에 II-2 제품 변경이 들어간다')

        # fix round 3 -- 새 요약 필드
        eq('table_added' in result['summary'] and 'table_removed' in result['summary'], True,
           'summary 에 table_added/table_removed 가 추가됐다')
        eq('by_kind' in result['summary'] and 'by_section' in result['summary'], True,
           'summary 에 kind별/section별 집계가 추가됐다')
        eq(sum(v.get('added', 0) + v.get('removed', 0) + v.get('changed', 0) + v.get('modified', 0)
               for v in result['summary']['by_kind'].values()),
           len(result['changes']), 'by_kind 합계는 전체 changes 개수와 같다')
        eq('top_text_sections' in result['summary'], True, 'summary 에 top_text_sections 추가됐다')
        eq(any(s.startswith('II-2') for s in result['summary']['top_text_sections']), True,
           'top_text_sections 에 실제 텍스트 변경이 있던 섹션(II-2)이 포함된다')

        # dart_diff.json 이 실제로 기록됐는지
        on_disk = tc.read_json(os.path.join(tc.ta_dir('테스트종목'), 'dart_diff.json'))
        eq(on_disk['status'], 'ok', 'dart_diff.json 저장 확인')

        # fix round 6 -- 압축본 dart_diff_highlights.json
        hl_path = os.path.join(tc.ta_dir('테스트종목'), 'dart_diff_highlights.json')
        compact = tc.read_json(hl_path)
        eq(sorted(compact), sorted(['latest', 'previous', 'summary', 'top_text_sections', 'highlights', 'modified', 'note']),
           '압축본은 지정된 키만 담는다')
        eq(compact['note'], '전체 변경점은 ta/dart_diff.json 에서 grep', '압축본 note')
        eq(all(c['change'] == 'modified' for c in compact['modified']) and len(compact['modified']) >= 1, True,
           '압축본 modified 는 modified 레코드만')
        eq(compact['highlights'], result['highlights'], '압축본 highlights 는 전체본과 같다')
        eq('changes' in on_disk, True, '전체본 dart_diff.json 은 changes 를 그대로 유지')

        manifest = tc.read_json(os.path.join(tc.ta_dir('테스트종목'), 'manifest.json'))
        eq(manifest['steps']['dart_diff']['status'], 'ok', 'manifest 에도 기록')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== fix round 6 -- 압축본은 전체본보다 훨씬 작다 ====================
# 실측처럼 표 행 변경이 대부분인 보고서: 전체본은 전부 담고 압축본은 highlights + modified 만.
NOISY_LATEST = LATEST_FULL.replace(
    '매출액은 120억원이다.',
    '매출액은 120억원이다.\n\n' + '\n\n'.join(f'품목{i} 계 - {i * 1000:,}({i % 97}.5%) {i * 7:,} {i * 3:,}' for i in range(300)))
with tempfile.TemporaryDirectory() as root:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = root
    try:
        data_d = tc.data_dir('압축종목')
        os.makedirs(data_d, exist_ok=True)
        with open(os.path.join(data_d, '_dart_FULL_사업보고서(2025.12)_20260318000001.txt'), 'w', encoding='utf-8') as f:
            f.write(PREV_FULL)
        with open(os.path.join(data_d, '_dart_FULL_반기보고서(2026.06)_20260318000003.txt'), 'w', encoding='utf-8') as f:
            f.write(NOISY_LATEST)
        td.run('압축종목')
        full_size = os.path.getsize(os.path.join(tc.ta_dir('압축종목'), 'dart_diff.json'))
        compact_size = os.path.getsize(os.path.join(tc.ta_dir('압축종목'), 'dart_diff_highlights.json'))
        eq(compact_size * 4 < full_size, True, f'압축본({compact_size}B)은 전체본({full_size}B)의 1/4 미만')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== run() -- 보고서 1편만 있으면 분할만, changes 비고 reason ====================
with tempfile.TemporaryDirectory() as root:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = root
    try:
        data_d = tc.data_dir('혼자종목')
        os.makedirs(data_d, exist_ok=True)
        with open(os.path.join(data_d, '_dart_FULL_사업보고서(2025.12)_20260318000001.txt'),
                  'w', encoding='utf-8') as f:
            f.write(PREV_FULL)

        result = td.run('혼자종목')
        eq(result['status'], 'ok', '1편이어도 분할 자체는 ok')
        eq(result['previous'], None, '직전 보고서가 없다')
        eq(result['changes'], [], '비교 대상이 없으니 changes 는 빈 목록')
        eq(len(result['reason']) > 0, True, '이유가 채워진다')
        eq(len(result['files']) > 0, True, '분할 파일은 그래도 만들어진다')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== run() -- DART 파일이 아예 없으면 failed ====================
with tempfile.TemporaryDirectory() as root:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = root
    try:
        os.makedirs(tc.data_dir('빈종목'), exist_ok=True)
        result = td.run('빈종목')
        eq(result['status'], 'failed', '파일이 없으면 failed')
        eq(len(result['reason']) > 0, True, 'failed 이유가 채워진다')
    finally:
        tc.PROJECT_ROOT = orig_root

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_dart_diff 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
