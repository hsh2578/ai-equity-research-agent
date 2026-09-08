import json, sys, os, time
sys.path.insert(0, "scripts")
sys.stdout.reconfigure(encoding='utf-8')
from dart_api import get_corp_code, get_all_reports
from kis_api import get_current_price, get_investor_trend, get_daily_price, get_all_financials

NAME, CODE = "에프에스티", "036810"
os.makedirs(f"data/{NAME}", exist_ok=True)

def retry(fn, *a, **k):
    for i in range(4):
        try:
            return fn(*a, **k)
        except Exception as e:
            print(f"  retry {i+1}: {type(e).__name__}", flush=True)
            time.sleep(2 * (i + 1))
    return None

cc = get_corp_code(NAME)
corp_code = cc[0] if isinstance(cc, (list, tuple)) else cc
print(f"[1] corp_code={corp_code}", flush=True)

fin = retry(get_all_financials, CODE, period="0")
json.dump(fin, open(f"data/{NAME}/data_kis_financials.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[2] KIS 재무 저장", flush=True)

kis = {
    "current_price": retry(get_current_price, CODE),
    "investor_trend": retry(get_investor_trend, CODE, 20),
    "daily_prices": retry(get_daily_price, CODE, 120),
}
json.dump(kis, open(f"data/{NAME}/data_kis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
cp = kis.get("current_price") or {}
print(f"[3] KIS 시세: 현재가 {cp.get('현재가')} / 시총 {cp.get('시가총액')}억 / PER {cp.get('PER')} / PBR {cp.get('PBR')}", flush=True)

reports = retry(get_all_reports, corp_code)
json.dump(reports, open(f"data/{NAME}/data_dart_reports.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[4] DART 보고서 {len(reports or [])}건", flush=True)
for i, r in enumerate((reports or [])[:6]):
    print(f"    [{i}] {r.get('type','?')} {r.get('report_nm','')} sections={list((r.get('sections') or {}).keys())[:5]}", flush=True)
print("[DONE] 에프에스티 수집 완료", flush=True)
