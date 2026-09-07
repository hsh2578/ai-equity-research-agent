import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dart_api import get_corp_code, get_all_report_rcept_nos, download_report_document, html_to_text

OUT = 'data/한국콜마'
os.makedirs(OUT, exist_ok=True)

corp_code, corp_name = get_corp_code('한국콜마')
print(f"corp_code={corp_code} name={corp_name}")

rcepts = get_all_report_rcept_nos(corp_code)
print(f"reports={len(rcepts)}")
for r in rcepts[:8]:
    print(" ", r)

json.dump(rcepts, open(f'{OUT}/_rcepts.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)
