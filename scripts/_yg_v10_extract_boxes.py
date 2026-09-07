"""워드 docx에서 박스별 본문 통째로 추출 → JSON 저장"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from docx import Document
from pathlib import Path

DOCX = 'output/와이지엔터/18-1_와이지엔터테인먼트_본문_편집용.docx'
OUT = 'scripts/_yg_v10_boxes.json'

doc = Document(DOCX)

boxes = []
cur_slide_num = ''
cur_slide_title = ''
cur_subheads_body = []  # 박스 내 (subhead, body_lines)
cur_box = None
cur_subhead = None
cur_subhead_lines = []


def commit_subhead():
    global cur_subhead, cur_subhead_lines
    if cur_subhead is not None and cur_box is not None:
        cur_box['subs'].append({'subhead': cur_subhead, 'body': '\n'.join(cur_subhead_lines)})
        cur_subhead = None
        cur_subhead_lines = []
    elif cur_subhead_lines and cur_box is not None:
        # subhead 없는 본문도 그대로
        cur_box['subs'].append({'subhead': '', 'body': '\n'.join(cur_subhead_lines)})
        cur_subhead_lines = []


def commit_box():
    global cur_box, cur_subhead, cur_subhead_lines
    commit_subhead()
    if cur_box is not None:
        boxes.append(cur_box)
        cur_box = None


for p in doc.paragraphs:
    style = p.style.name
    text = p.text.strip()
    if not text: continue
    # 도표/카피/출처 메모 제외
    if text.startswith('[도표') or text.startswith('★') or '도표 권장' in text or '도표 추가' in text: continue
    if text.startswith('[좌측 카피]') or text.startswith('[자료:'): continue
    if text.startswith('자료:'): continue
    if text.startswith('📊'): continue

    if style == 'Heading 1' and 'Slide' in text:
        commit_box()
        m = re.match(r'Slide\s+([\w-]+)', text)
        if m:
            cur_slide_num = m.group(1)
            cur_slide_title = text
    elif style == 'Heading 2' and '박스' in text:
        commit_box()
        # 박스 시작 시 박스 외부에 쌓인 단락(목차 등) 버림
        cur_subhead_lines = []
        cur_subhead = None
        m = re.match(r'박스\s*(\d+):\s*(.+)', text)
        if m:
            cur_box = {
                'slide_num': cur_slide_num,
                'slide_title': cur_slide_title,
                'box_no': m.group(1),
                'box_title': m.group(2),
                'subs': []
            }
    elif style == 'Heading 3' or style == 'Heading 4':
        # 소제목 (subhead)
        commit_subhead()
        cur_subhead = text
    else:
        # 본문 단락 — `*`로 시작하는 줄은 subhead (소제목)로 처리
        if text.startswith('*'):
            commit_subhead()
            cur_subhead = text.lstrip('*').strip()
        else:
            cur_subhead_lines.append(text)

commit_box()

# 출력
Path(OUT).parent.mkdir(exist_ok=True)
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(boxes, f, ensure_ascii=False, indent=2)

print(f'박스 추출: {len(boxes)}개')
for b in boxes:
    total_len = sum(len(s['body']) for s in b['subs'])
    print(f'  {b["slide_num"]:>5}  박스{b["box_no"]}  ({total_len:>4}자, sub {len(b["subs"])})  {b["box_title"][:35]}')
