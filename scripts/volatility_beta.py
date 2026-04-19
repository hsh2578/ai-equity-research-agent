"""
STEP 1.6: 변동성·베타 계산 (100일 회귀, KOSPI200/KOSDAQ150 기준)

사용법:
    python scripts/volatility_beta.py {종목명} {종목코드} [시장코드]
    시장코드: 069500 (KOSPI200 ETF, 기본) / 229200 (KOSDAQ150 ETF)
"""
import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from kis_api import get_daily_price


def main(stock_name, stock_code, mkt_code='069500'):
    stock_daily = get_daily_price(stock_code, 100)
    mkt_daily = get_daily_price(mkt_code, 100)

    if not stock_daily or not mkt_daily:
        print(f"[ERR] 일봉 데이터 없음")
        return 1

    stock_closes = np.array([float(r['종가']) for r in stock_daily[::-1]])
    mkt_closes = np.array([float(r['종가']) for r in mkt_daily[::-1]])
    stock_rets = np.diff(np.log(stock_closes))
    mkt_rets = np.diff(np.log(mkt_closes))

    n = min(len(stock_rets), len(mkt_rets))
    stock_rets, mkt_rets = stock_rets[:n], mkt_rets[:n]

    cov = np.cov(stock_rets, mkt_rets)[0, 1]
    var_mkt = np.var(mkt_rets)
    beta = cov / var_mkt if var_mkt else 0
    corr = np.corrcoef(stock_rets, mkt_rets)[0, 1]
    r2 = corr ** 2
    vol_annual = float(np.std(stock_rets) * np.sqrt(252))

    out = {
        'beta': float(beta),
        'r2': float(r2),
        'vol_annual': vol_annual,
        'market_code': mkt_code,
        'n_days': int(n),
    }
    os.makedirs(f'data/{stock_name}', exist_ok=True)
    path = f'data/{stock_name}/_volatility_beta.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f"[OK] Beta={beta:.2f} (R²={r2:.3f})  σ_annual={vol_annual*100:.1f}%  (mkt={mkt_code}, n={n})")
    print(f"[OK] saved: {path}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("usage: python scripts/volatility_beta.py {종목명} {종목코드} [시장코드]")
        sys.exit(1)
    stock_name = sys.argv[1]
    stock_code = sys.argv[2]
    mkt_code = sys.argv[3] if len(sys.argv) > 3 else '069500'
    sys.exit(main(stock_name, stock_code, mkt_code))
