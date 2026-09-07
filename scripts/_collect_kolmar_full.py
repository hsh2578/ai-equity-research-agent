import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dart_api import download_report_document, html_to_text

OUT = 'data/한국콜마'
TARGETS = [
    ('20260318001196', 'ANNUAL2025'),   # 사업보고서 2025.12
    ('20260814002721', 'H1_2026'),      # 반기보고서 2026.06
]
for rcept, tag in TARGETS:
    files = download_report_document(rcept)
    if not files:
        print(f"[FAIL] {tag}")
        continue
    # 가장 큰 파일 = 본문
    best = max(files.items(), key=lambda kv: len(kv[1]))
    text = html_to_text(best[1])
    p = f'{OUT}/_dart_FULL_{tag}.txt'
    open(p, 'w', encoding='utf-8').write(text)
    print(f"[OK] {tag} files={len(files)} main={best[0]} chars={len(text):,} -> {p}")
