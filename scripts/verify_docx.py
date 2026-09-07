"""verify_docx.py -- 위닝펀드 Word(.docx) 산출물 전용 검증.

검사:
  D1 도표 이미지 수 == chart_plan 의 data 준비 도표 수
  D2 도표 캡션('도표 N.') 수 == 도표 이미지 수
  D3 모든 도표 아래 '자료 :' 출처선 존재 (출처선 수 >= 도표 수)
  D4 이모지/placeholder 잔재 0 (★☆ 는 허용)
  D5 표지 필수 필드(투자의견 등급 + 목표주가 + 현재가) 존재
  D6 섹션 커버리지 (정규 섹션 헤더 등장 수) -- 경고용

CLI: python scripts/verify_docx.py {종목명} [docx_path] [chart_plan_path]
종료코드: FAIL 있으면 1.
"""
import sys, io, json, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from pathlib import Path
from docx import Document

# ★(U+2605)·☆(U+2606)은 별점 표기로 허용 -- U+2600~26FF 범위에서 carve-out (D4 주석 "★☆ 허용"과 일치)
_EMOJI = re.compile('[\U0001F000-\U0001FAFF\U00002600-\U00002604\U00002607-\U000026FF\U0001F1E6-\U0001F1FF]')
PLACEHOLDERS = ['lorem', 'ipsum', 'xxxx', 'todo', 'tbd', '{stock}', '{author}', '{industry}',
                '도표 nn', '도표 NN', '자료 : \n']

SECTION_TITLE_HINTS = ['투자', '카탈리스트', '기업', '산업', '경쟁', '경영', '재무', '밸류',
                       'esg', 'ESG', '시나리오', '리스크', '실적', '수급', '실행', 'Executive']


def _all_text(doc):
    parts = [p.text for p in doc.paragraphs]
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return parts


def verify(docx_path, plan_path):
    doc = Document(docx_path)
    plan = json.load(open(plan_path, encoding='utf-8')) if Path(plan_path).exists() else {'charts': []}
    ready = [c for c in plan.get('charts', []) if c.get('data') is not None]
    n_ready = len(ready)

    paras = doc.paragraphs
    texts = _all_text(doc)
    fulltext = '\n'.join(texts)

    results = []  # (level, code, msg)

    # D1 이미지 수
    n_img = len(doc.inline_shapes)
    if n_img == n_ready:
        results.append(('PASS', 'D1', f'도표 이미지 {n_img}개 == 준비 도표 {n_ready}개'))
    else:
        results.append(('FAIL', 'D1', f'도표 이미지 {n_img}개 != 준비 도표 {n_ready}개'))

    # D2 캡션 수
    n_cap = sum(1 for p in paras if p.text.strip().startswith('도표 '))
    if n_cap == n_ready:
        results.append(('PASS', 'D2', f"'도표 N.' 캡션 {n_cap}개 == 도표 {n_ready}개"))
    else:
        results.append(('FAIL', 'D2', f"캡션 {n_cap}개 != 도표 {n_ready}개"))

    # D3 출처선
    n_src = sum(1 for p in paras if p.text.strip().startswith('자료 :'))
    if n_src >= n_ready:
        results.append(('PASS', 'D3', f"'자료 :' 출처선 {n_src}개 >= 도표 {n_ready}개"))
    else:
        results.append(('FAIL', 'D3', f"출처선 {n_src}개 < 도표 {n_ready}개"))

    # D4 이모지/placeholder
    emoji_hit = _EMOJI.findall(fulltext)
    ph_hit = [p for p in PLACEHOLDERS if p.lower() in fulltext.lower()]
    if not emoji_hit and not ph_hit:
        results.append(('PASS', 'D4', '이모지/placeholder 잔재 없음'))
    else:
        results.append(('FAIL', 'D4', f'이모지 {len(emoji_hit)}건 / placeholder {ph_hit}'))

    # D5 표지 필수
    has_rating = any(r in fulltext for r in ('BUY', 'HOLD', 'SELL', '매수', '중립', '매도'))
    has_target = '목표주가' in fulltext
    has_current = ('현재가' in fulltext)
    if has_rating and has_target and has_current:
        results.append(('PASS', 'D5', '표지 투자의견·목표주가·현재가 존재'))
    else:
        results.append(('FAIL', 'D5', f'표지 누락 (rating={has_rating}, target={has_target}, current={has_current})'))

    # D6 섹션 커버리지 (경고)
    head_texts = [p.text for p in paras if p.text.strip() and len(p.text.strip()) < 40]
    n_sec = sum(1 for h in SECTION_TITLE_HINTS if any(h in t for t in head_texts))
    if n_sec >= 8:
        results.append(('PASS', 'D6', f'섹션 헤더 {n_sec}/14 종 등장'))
    else:
        results.append(('WARN', 'D6', f'섹션 헤더 {n_sec}종만 등장 (8+ 권장)'))

    return results, {'images': n_img, 'ready': n_ready, 'captions': n_cap, 'sources': n_src}


def main():
    if len(sys.argv) < 2:
        print('usage: python scripts/verify_docx.py {종목명} [docx_path] [chart_plan_path]')
        sys.exit(1)
    stock = sys.argv[1]
    docx_path = sys.argv[2] if len(sys.argv) > 2 else f'output/{stock}/report_{stock}.docx'
    plan_path = sys.argv[3] if len(sys.argv) > 3 else f'data/{stock}/chart_plan.json'
    if not Path(docx_path).exists():
        print(f'[ERROR] docx 없음: {docx_path}')
        sys.exit(1)
    results, stats = verify(docx_path, plan_path)
    print(f'=== verify_docx: {docx_path} ===')
    print(f'    (이미지 {stats["images"]} / 준비도표 {stats["ready"]} / 캡션 {stats["captions"]} / 출처선 {stats["sources"]})')
    nfail = 0
    for level, code, msg in results:
        print(f'  [{level}] {code}: {msg}')
        if level == 'FAIL':
            nfail += 1
    print(f'--- {len(results)}개 검사, FAIL {nfail}개 ---')
    sys.exit(1 if nfail else 0)


if __name__ == '__main__':
    main()
