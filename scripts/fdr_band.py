"""
STEP 1.7: 5년 PER/PBR 밴드 (FDR 연말 종가 정확 조회)

사용법:
    python scripts/fdr_band.py {종목명} {종목코드}
"""
import sys
import io
import os
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import FinanceDataReader as fdr
from kis_api import get_current_price


def main(stock_name, stock_code):
    px = get_current_price(stock_code)
    current_per = float(px.get('PER', 0))
    current_pbr = float(px.get('PBR', 0))
    current_price = int(px.get('현재가', 0))

    df = fdr.DataReader(stock_code, '2020-01-01', '2026-12-31')
    year_end = df.groupby(df.index.year).tail(1)
    closes = {int(idx.year): int(row['Close']) for idx, row in year_end.iterrows()}

    fs_path = f'data/{stock_name}/financial_summary.json'
    if not os.path.exists(fs_path):
        print(f"[ERR] {fs_path} 없음. financial_summary.py 먼저 실행.")
        return 1
    d = json.load(open(fs_path, encoding='utf-8'))
    fin = d.get('financials', {})

    per_series, pbr_series = [], []
    for y in sorted(closes.keys()):
        yf = fin.get(str(y), {})
        eps = yf.get('eps')
        bps = yf.get('bps')
        if eps and eps > 0:
            per_series.append(closes[y] / eps)
        if bps and bps > 0:
            pbr_series.append(closes[y] / bps)

    per_mean = float(np.mean(per_series)) if per_series else 0
    per_std = float(np.std(per_series)) if per_series else 0
    pbr_mean = float(np.mean(pbr_series)) if pbr_series else 0
    pbr_std = float(np.std(pbr_series)) if pbr_series else 0
    current_per_z = (current_per - per_mean) / per_std if per_std else 0
    current_pbr_z = (current_pbr - pbr_mean) / pbr_std if pbr_std else 0

    out = {
        'closes': closes,
        'per_series': per_series, 'pbr_series': pbr_series,
        'per_mean': per_mean, 'per_std': per_std,
        'pbr_mean': pbr_mean, 'pbr_std': pbr_std,
        'current_per': current_per, 'current_per_z': current_per_z,
        'current_pbr': current_pbr, 'current_pbr_z': current_pbr_z,
        'current_price': current_price,
    }
    os.makedirs(f'data/{stock_name}', exist_ok=True)
    path = f'data/{stock_name}/_per_band.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f"[OK] 5Y PER: mean={per_mean:.2f}x, std={per_std:.2f}, current={current_per:.2f}x (z={current_per_z:+.2f}σ)")
    print(f"[OK] 5Y PBR: mean={pbr_mean:.2f}x, std={pbr_std:.2f}, current={current_pbr:.2f}x (z={current_pbr_z:+.2f}σ)")
    print(f"[OK] saved: {path}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("usage: python scripts/fdr_band.py {종목명} {종목코드}")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
