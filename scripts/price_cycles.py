"""price_cycles.py -- 과거 주가 사이클 자동 탐지.

배경(2026-09 위닝펀드 수상작 정독): 수상작의 가장 강한 논증 장치는 과거 사이클 유비다.

    "직전 사이클(2024.10~2025.08) 와이지 주가가 37,000원 -> 107,400원 +190%
     상승했을 때(FDR 실측), 그 핵심 트리거가 '메가 IP 재계약과 월드투어'였다.
     본 리포트는 이번 사이클에서 그 자리를 빅뱅 20주년 월드투어가 대체한다고 본다."

구조는 셋이다. (1) 과거 큰 움직임을 실측으로 특정 (2) 그때의 트리거 규명
(3) 지금의 트리거와 1:1 대응. 대응이 성립하지 않으면 그 논거는 약하다.

이 모듈은 **(1)만** 한다. 트리거 규명은 데이터가 아니라 판단이므로 저자가 쓴다.
다만 저자가 구간이나 폭을 지어내지 못하도록 시작/끝/변동률을 실측으로 고정한다.

실측 비교(1만자당 등장): 수상작 1.1회 vs 우리 0.3회. 우리는 "저점 대비 +104.6%"
같은 단순 수익률만 썼는데, 그건 사이클이 아니다 -- 언제 시작해 언제 끝났는지가 없다.

사용: python scripts/price_cycles.py {종목명} {종목코드}
"""
import io
import json
import os
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

MIN_MOVE_PCT = 30      # 이보다 작은 움직임은 사이클이 아니다 (노이즈)
RETRACE_PCT = 15       # 이보다 작은 되돌림은 사이클을 끊지 않는다


def _label(a, b):
    return f'{a[:7]} ~ {b[:7]}'


def _months(a, b):
    ya, ma = int(a[:4]), int(a[5:7])
    yb, mb = int(b[:4]), int(b[5:7])
    return (yb - ya) * 12 + (mb - ma)


def find_cycles(series, min_move=MIN_MOVE_PCT, retrace=RETRACE_PCT):
    """[(date, close), ...] -> 사이클 목록. **최신 사이클이 앞에 온다.**

    ZigZag 방식: 방향이 유지되는 동안 극점을 갱신하고, retrace% 이상 반대로
    꺾이면 한 구간을 확정한다. 확정된 구간 중 변동률이 min_move 이상인 것만 남긴다.
    """
    pts = [(d, float(p)) for d, p in (series or []) if p is not None]
    if len(pts) < 2:
        return []

    # ZigZag 전환점 추출
    piv = [pts[0]]
    direction = 0           # 0 미정 / 1 상승 / -1 하락
    ext = pts[0]
    for d, p in pts[1:]:
        if direction >= 0 and p >= ext[1]:
            ext = (d, p)
            direction = 1
            continue
        if direction <= 0 and p <= ext[1]:
            ext = (d, p)
            direction = -1
            continue
        if not ext[1]:
            continue
        moved = abs(p - ext[1]) / ext[1] * 100
        if moved >= retrace:
            piv.append(ext)
            ext = (d, p)
            direction = 1 if p > piv[-1][1] else -1
    piv.append(ext)

    out = []
    for (d0, p0), (d1, p1) in zip(piv, piv[1:]):
        if not p0 or d0 == d1:
            continue
        chg = (p1 - p0) / p0 * 100
        if abs(chg) < min_move:
            continue
        out.append({
            'start': d0, 'end': d1,
            'start_price': round(p0), 'end_price': round(p1),
            'change_pct': round(chg, 1),
            'direction': 'up' if chg > 0 else 'down',
            'label': _label(d0, d1),
            'months': _months(d0, d1),
        })
    out.reverse()          # 최신 사이클이 먼저 -- 본문은 '직전 사이클'을 인용한다
    return out


def main(stock_name, stock_code, years=5):
    try:
        import FinanceDataReader as fdr
    except ImportError:
        print('[ERR] FinanceDataReader 가 없다: pip install finance-datareader')
        return 1
    from datetime import datetime
    end = datetime.now()
    start = end.replace(year=end.year - years)
    df = fdr.DataReader(stock_code, start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
    if df is None or df.empty:
        print(f'[ERR] {stock_code} 시세 조회 실패')
        return 1
    # 주 단위로 줄여 일간 노이즈를 없앤다
    w = df['Close'].resample('W').last().dropna()
    series = [(d.strftime('%Y-%m-%d'), float(v)) for d, v in w.items()]
    cycles = find_cycles(series)

    out = {'stock': stock_name, 'code': stock_code,
           'observations': len(series),
           'period': f'{series[0][0]} ~ {series[-1][0]}' if series else '',
           'min_move_pct': MIN_MOVE_PCT, 'retrace_pct': RETRACE_PCT,
           'cycles': cycles}
    os.makedirs(f'data/{stock_name}', exist_ok=True)
    path = f'data/{stock_name}/_price_cycles.json'
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

    print(f'[OK] {stock_name} {years}년 주간 종가 {len(series)}개 -> 사이클 {len(cycles)}개')
    for c in cycles[:6]:
        arrow = '상승' if c['direction'] == 'up' else '하락'
        print(f"   {c['label']} ({c['months']:2}개월) {arrow} "
              f"{c['start_price']:,} -> {c['end_price']:,}원  {c['change_pct']:+.1f}%")
    if not cycles:
        print('   (30% 이상 움직인 구간이 없다 -- 사이클 유비를 쓰지 말 것)')
    print(f'[OK] saved: {path}')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
