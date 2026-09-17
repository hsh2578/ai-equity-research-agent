"""ta_kind_ir 테스트: 목록 HTML 파싱(네트워크 없음).

실행: python tests/test_ta_kind_ir.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_kind_ir as k  # noqa: E402

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


HTML = '''<tr><td class="first txc">3</td><td><a href="#">에프에스티</a></td><td class="txc"> 2026-04-01 </td>
<td><a href="#" onclick="fnDetailView('18269','2'); return false;">기업설명회(IR) 개최</a></td>
<td class="txc"><a href="/external/dst/irReference/18269/FST_IR자료(2026년).pdf" class="btn attach_file">x</a></td></tr>
<tr><td class="first txc">2</td><td><a href="#">에프에스티</a></td><td class="txc"> 2025-11-17 </td>
<td><a href="#">기업설명회(IR) 개최</a></td><td class="txc"> </td></tr>
<tr><td class="first txc">1</td><td><a href="#">에프에스티</a></td><td class="txc"> 2025-07-28 </td>
<td><a href="#">기업설명회(IR) 개최</a></td>
<td class="txc"><a href="/external/dst/irReference/17050/FST_IR자료(2025년) .pdf">y</a></td></tr>'''
rows = k.parse_rows(HTML)
eq(len(rows), 2, '첨부 있는 행만')
eq(rows[0], {'date': '2026-04-01', 'seq': '18269', 'url_path': '/external/dst/irReference/18269/FST_IR자료(2026년).pdf', 'filename': 'FST_IR자료(2026년).pdf'}, '행 파싱')
eq(rows[1]['filename'], 'FST_IR자료(2025년) .pdf', '파일명 공백 유지(URL 은 quote 로)')
eq(k.parse_rows('<table></table>'), [], '없으면 빈 리스트')

print(f'ta_kind_ir 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for label, want, got in _failed:
    print(f'  [FAIL] {label}: want={want!r} got={got!r}')
sys.exit(1 if _failed else 0)
