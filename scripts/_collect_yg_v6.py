import json, sys, os, time
sys.path.insert(0, "scripts")
sys.stdout.reconfigure(encoding='utf-8')
from dart_api import get_corp_code, get_all_reports, get_consolidated_statements
from kis_api import get_current_price, get_investor_trend, get_daily_price, get_all_financials

NAME, CODE = "와이지엔터", "122870"
os.makedirs(f"data/{NAME}", exist_ok=True)

def retry(fn, *a, **k):
    for i in range(4):
        try:
            return fn(*a, **k)
        except Exception as e:
            print(f"  retry {i+1}: {type(e).__name__}", flush=True)
            time.sleep(2 * (i + 1))
    return None

cc = get_corp_code("와이지엔터테인먼트")
corp = cc[0] if isinstance(cc, (list, tuple)) else cc
print(f"[1] corp_code={corp}", flush=True)

kis = {"current_price": retry(get_current_price, CODE),
       "investor_trend": retry(get_investor_trend, CODE, 20),
       "daily_prices": retry(get_daily_price, CODE, 120)}
json.dump(kis, open(f"data/{NAME}/data_kis.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
cp = kis.get("current_price") or {}
print(f"[2] 현재가 {cp.get('현재가')} / 시총 {cp.get('시가총액')}억 / PER {cp.get('PER')} / PBR {cp.get('PBR')} / EPS {cp.get('EPS')} / BPS {cp.get('BPS')}", flush=True)
print(f"    52주 {cp.get('52주최저')}~{cp.get('52주최고')}", flush=True)
it = kis.get("investor_trend") or {}
print(f"    수급 {{k:v for k,v in it.items() if k!='detail'}}".replace("{k:v for k,v in it.items() if k!='detail'}", str({k: v for k, v in it.items() if k != 'detail'})), flush=True)

fin = retry(get_all_financials, CODE, period="0")
json.dump(fin, open(f"data/{NAME}/data_kis_financials.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[3] KIS 재무 income rows={len((fin or {}).get('income') or [])}", flush=True)

dart_fin = {}
for y in range(2021, 2026):
    r = retry(get_consolidated_statements, corp, str(y))
    dart_fin[str(y)] = r
    n = len((r or {}).get('list') or [])
    print(f"    DART {y} items {n}", flush=True)
    time.sleep(0.4)
json.dump(dart_fin, open(f"data/{NAME}/data_dart_financials.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

reports = retry(get_all_reports, corp)
json.dump(reports, open(f"data/{NAME}/data_dart_reports.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[4] DART 보고서 {len(reports or [])}건", flush=True)
for i, r in enumerate((reports or [])[:5]):
    print(f"    [{i}] {r.get('report_nm','')}", flush=True)
print("[DONE]", flush=True)
