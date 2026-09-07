"""와이지엔터 STEP 1 데이터 재수집 (v5.4 규칙 8 -- 11일 경과 재수집)"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, 'scripts')

from dart_api import get_corp_code, get_all_reports
from kis_api import get_current_price, get_investor_trend, get_daily_price, get_all_financials

STOCK = "와이지엔터"
CODE = "122870"
os.makedirs(f"data/{STOCK}", exist_ok=True)

# 1. KIS 시세/수급/일봉
print("[1] KIS 시세/수급/일봉 수집...")
kis = {
    "current_price": get_current_price(CODE),
    "investor_trend": get_investor_trend(CODE, 20),
    "daily_prices": get_daily_price(CODE, 120),
}
json.dump(kis, open(f"data/{STOCK}/data_kis.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
px = kis["current_price"]
print(f"  현재가={px.get('현재가')} 시총={px.get('시가총액')}억 PER={px.get('PER')} PBR={px.get('PBR')} EPS={px.get('EPS')} 52H={px.get('52주최고')} 52L={px.get('52주최저')}")
it = kis["investor_trend"]
print(f"  외국인20일={it.get('외국인_순매수')} 기관20일={it.get('기관_순매수')} 개인20일={it.get('개인_순매수')} (단위:주)")

# 2. KIS 재무 7개 엔드포인트
print("[2] KIS 재무 통합...")
fin = get_all_financials(CODE, period="0")
json.dump(fin, open(f"data/{STOCK}/data_kis_financials.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("  완료")

# 3. DART 사업보고서 (본문만)
print("[3] DART 사업보고서 수집...")
corp_code, stock_code = get_corp_code(STOCK)
if not corp_code:
    corp_code, stock_code = get_corp_code("와이지엔터테인먼트")
print(f"  corp_code={corp_code} stock_code={stock_code}")
reports = get_all_reports(corp_code)
json.dump(reports, open(f"data/{STOCK}/data_dart_reports.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
for i, r in enumerate(reports[:7]):
    print(f"  [{i}] {r.get('type','?')} {r.get('report_nm','')} sections={list(r.get('sections',{}).keys())}")

print("[DONE] _collect_yg 완료")
