"""
STEP 1.7: 5년 PER/PBR 밴드 (FDR 연말 종가 정확 조회)

사용법:
    python scripts/fdr_band.py {종목명} {종목코드}
출력: data/{종목명}/_per_band.json

v5.7 가드 이식 (fdr_band_us.py 의 v5.5/v5.6 가드를 KR 로 역이식)
-------------------------------------------------------------
초판은 연말 종가와 EPS/BPS 를 나누어 평균/표준편차/z-score 를 그대로 냈다.
그 결과 리포트가 노이즈를 "5년 평균 대비 저평가" 로 단정할 수 있었다.
US 판이 실제로 잡아낸 사고(AMD PER 56 -> 278 -> 121, 평균 122 / 현재 121 인데
표준편차가 80) 는 한국 사이클주에도 그대로 있다 -- 풍산 PER 3.6 -> 20.3,
OCI홀딩스 1.7 -> 34,062, 카카오 17 -> 308.

이식한 가드 4종:
  (1) 표본 MIN_SAMPLES 개 미만이면 밴드/z-score 산출 거부
      -> per_band_valid / pbr_band_valid = False
  (2) 변동계수(std/mean) > NOISY_CV 이면 밴드 무효 + 경고
  (3) 진행 중인 당해년도 제외. FDR 은 오늘까지의 일봉을 주므로
      groupby(year).tail(1) 이 '오늘 종가 = 올해 연말 종가' 를 만든다.
      그 해 재무가 분기 누적이면 close/eps 가 통째로 가짜 배수가 되고,
      그 오염된 시계열로 평균과 변동계수를 재게 된다. 달력연도가 끝난 해만 쓴다.
  (4) 주당 기준(액면분할 등) 불일치 연도 제외. FDR 종가는 수정주가인데
      KIS 재무비율 EPS/BPS 가 분할 전 기준이면 배수가 10배 틀린다.

KR 특유 사정 -- 발행주식수 (가드 4 가 KR 에서 휴면인 이유)
  KIS 재무비율은 연도별 발행주식수를 주지 않는다. 대신 그 해 EPS/BPS 를
  원 단위로 직접 준다. 그래서 BPS 는 **그 해 bps 필드가 1순위**이고, 없을 때만
  자기자본(억원) / **그 해 명시 주식수** 로 역산한다. 명시 주식수가 없으면
  **BPS/PBR 을 산출하지 않고** 사유를 notes 에 남긴다. 오늘 주식수로 과거
  자기자본을 나누면 자사주 소각/증자 기업이 전부 틀린다 -- 틀린 숫자보다
  '없다'가 낫다.

  주식수를 순이익(억원)*1e8 / EPS(원) 로 역산하는 방법은 **쓰지 않는다.**
  실데이터로 검증했더니 이 역산은 연결 순이익(비지배 포함)을 지배주주 EPS 로
  나누는 꼴이라 지주사/저마진 연도에서 통째로 어긋났다:
    두산 2021 ratio 4.21 / 2025 4.34 (지주사, 매년 일정 -- 분할이 아니다)
    GS리테일 2024 4.69, 한국콜마 2023 4.68 (순이익이 거의 0 인 해)
    에스엠 2024 0.04 (순이익 8억, EPS 778원)
  이 값으로 연도를 제외하면 **분산이 큰 해가 조용히 지워져** 노이즈 밴드가
  valid 로 뒤집힌다(에스엠 PER 97배 연도가 사라지고 CV 0.38 로 '유효' 판정).
  가드의 취지와 정반대다. 따라서 basis_problem 은 **명시 주식수가 있을 때만**
  판정한다. 현재 KR financial_summary 에는 그 필드가 없어 사실상 휴면이며,
  액면분할로 인한 배수 왜곡은 가드 2(변동계수)가 대신 잡는다.

출력 키 호환: 기존 키(closes / per_series / pbr_series / per_mean / per_std /
pbr_mean / pbr_std / current_per / current_per_z / current_pbr / current_pbr_z /
current_price) 는 전부 보존한다. generate_all.py 검증 #11, verify_numbers.py
B16/B23, build_snapshot.py 가 이 파일을 읽는다.
"""
import sys
import io
import os
import json
from datetime import date

# 이미 UTF-8 로 감싸져 있으면 다시 감싸지 않는다 (두 번 감싸면 먼저 만든 래퍼가
# GC 될 때 buffer 를 닫아 이 모듈을 import 한 쪽의 stdout 이 죽는다).
if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

MIN_SAMPLES = 3
NOISY_CV = 0.6          # 변동계수(std/mean) 이 값을 넘으면 밴드 해석 무의미
BASIS_RANGE = 3.0       # 최신 기준 주식수 대비 허용 배수 (넘으면 액면분할 등 기준 혼재)
EOK = 1e8               # 1억 (financial_summary 의 금액 단위가 억원이다)


def confirmed_year_closes(year_rows, current_year):
    """[(연도, 종가)] -> ({연도: 종가}, [제외 연도]).

    달력연도가 끝나야 '연말 종가'가 존재한다. 진행 중인 당해년도의 마지막
    거래일 종가는 연말 종가가 아니므로 밴드에서 뺀다 (가드 3).
    """
    closes, excluded = {}, []
    for y, close in year_rows:
        y = int(y)
        if y >= current_year:
            excluded.append(y)
            continue
        closes[y] = int(close)
    return closes, sorted(set(excluded))


def year_shares(year_data):
    """그 연도의 **명시** 발행주식수(주). 없거나 0 이면 None.

    순이익/EPS 역산은 하지 않는다 (모듈 docstring 의 실측 근거 참조).
    추정치로 BPS 를 만들거나 연도를 제외하면 밴드가 조용히 왜곡된다.
    """
    v = (year_data or {}).get('shares_outstanding')
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


def year_bps(year_data):
    """그 연도의 BPS(원). bps 필드 우선, 없으면 자기자본 / **그 연도** 주식수.

    오늘 주식수로 과거 자기자본을 나누지 않는다. 주식수를 못 구하면 None --
    추정하지 않는다.
    """
    yd = year_data or {}
    for k in ('bps', 'book_value_per_share'):
        v = yd.get(k)
        if v:
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    equity = yd.get('total_equity')
    shares = year_shares(yd)
    if equity and shares:
        return float(equity) * EOK / shares
    return None


def basis_problem(year_data, ref_shares):
    """연도 전체를 버려야 하는 주당 기준 불일치인가. 사유 문자열 또는 None.

    **명시 주식수가 있는 연도에만 판정한다.** KR 재무비율에는 그 필드가 없어
    현재는 휴면이다 -- 역산 주식수로 판정하면 저마진 연도가 통째로 지워진다.
    """
    shares = year_shares(year_data)
    if not shares or not ref_shares:
        return None
    ratio = shares / float(ref_shares)
    if ratio > BASIS_RANGE or ratio < 1.0 / BASIS_RANGE:
        return (f'주식수 {shares:,.0f} 가 최신 기준 {ref_shares:,.0f} 의 {ratio:.2f}배 - '
                f'주당 기준 불일치(액면분할 미반영 추정)')
    return None


def build_series(closes, fin, ref_shares=None):
    """확정 연도 종가 + 연도별 재무로 PER/PBR 시계열을 만든다.

    반환: {per_series, pbr_series, detail, notes, skipped}
      - skipped : {연도: 제외 사유}
      - notes   : 산출 거부/부분 제외 사유 (그대로 warnings 로 나간다)
    """
    per_series, pbr_series, detail, notes = [], [], {}, []
    skipped, no_shares = {}, []

    for y in sorted(closes):
        yd = fin.get(str(y))
        if not yd:
            continue
        prob = basis_problem(yd, ref_shares)
        if prob:
            skipped[str(y)] = prob
            continue

        close = closes[y]
        eps = yd.get('eps')
        bps = year_bps(yd)
        if bps is None and yd.get('total_equity'):
            no_shares.append(str(y))

        row = {'close': int(close), 'eps': eps,
               'bps': round(bps, 2) if bps else None}

        if eps and float(eps) > 0:
            per = close / float(eps)
            per_series.append(per)
            row['per'] = round(per, 2)

        if bps and bps > 0:
            pbr = close / bps
            pbr_series.append(pbr)
            row['pbr'] = round(pbr, 2)

        detail[str(y)] = row

    if no_shares:
        notes.append(
            f'{", ".join(no_shares)}년 BPS/발행주식수 없음 - BPS/PBR 산출 거부. '
            f'오늘 주식수로 과거 자기자본을 나누면 자사주소각/증자 기업이 전부 틀린다.')
    if skipped:
        notes.append(
            f'{", ".join(sorted(skipped))}년 제외 - 주당 기준 불일치. '
            f'FDR 종가는 수정주가인데 재무가 액면분할 전 기준이면 배수가 10배 틀린다.')
    return {'per_series': per_series, 'pbr_series': pbr_series,
            'detail': detail, 'notes': notes, 'skipped': skipped}


def band_stats(series, label):
    """(mean, std, valid, notes). 표본 부족/변동계수 초과면 valid=False.

    표본이 MIN_SAMPLES 미만이면 평균 자체를 만들지 않는다(0.0). 변동계수
    초과는 평균은 남기되 무효로 표시한다 -- 연도별 값을 직접 제시할 때 쓴다.
    """
    notes = []
    if len(series) < MIN_SAMPLES:
        notes.append(
            f'{label} 표본 {len(series)}개 (<{MIN_SAMPLES}) - 밴드/z-score 산출 거부. '
            f'리포트에 "5년 평균 대비" 표현 금지.')
        return 0.0, 0.0, False, notes
    mean = float(np.mean(series))
    std = float(np.std(series))
    cv = std / mean if mean else 99
    if cv > NOISY_CV:
        notes.append(
            f'{label} 변동계수 {cv:.2f} (>{NOISY_CV}) - 밴드 분산이 너무 커서 '
            f'z-score 해석 무의미. "역사적 고평가/저평가" 단정 금지, 연도별 값 직접 제시할 것.')
        return mean, std, False, notes
    return mean, std, True, notes


def main(stock_name, stock_code):
    import FinanceDataReader as fdr
    from kis_api import get_current_price

    px = get_current_price(stock_code)
    current_per = float(px.get('PER', 0))
    current_pbr = float(px.get('PBR', 0))
    current_price = int(px.get('현재가', 0))
    market_cap_uk = float(px.get('시가총액', 0) or 0)

    # 주당 기준 대조용 최신 주식수 = 시가총액(억원)*1e8 / 현재가(원)
    ref_shares = (market_cap_uk * EOK / current_price) if (market_cap_uk and current_price) else None

    fs_path = f'data/{stock_name}/financial_summary.json'
    if not os.path.exists(fs_path):
        print(f"[ERR] {fs_path} 없음. financial_summary.py 먼저 실행.")
        return 1
    d = json.load(open(fs_path, encoding='utf-8'))
    fin = d.get('financials', {})
    if not fin:
        print("[ERR] financials 비어있음.")
        return 1

    this_year = date.today().year
    df = fdr.DataReader(stock_code, '2020-01-01', f'{this_year}-12-31')
    year_end = df.groupby(df.index.year).tail(1)
    rows = [(int(idx.year), int(row['Close'])) for idx, row in year_end.iterrows()]
    closes, excluded_years = confirmed_year_closes(rows, this_year)

    built = build_series(closes, fin, ref_shares)
    per_series = built['per_series']
    pbr_series = built['pbr_series']
    warnings = list(built['notes'])

    per_mean, per_std, per_valid, per_notes = band_stats(per_series, 'PER')
    pbr_mean, pbr_std, pbr_valid, pbr_notes = band_stats(pbr_series, 'PBR')
    warnings += per_notes + pbr_notes

    current_per_z = (current_per - per_mean) / per_std if (per_std and current_per) else 0
    current_pbr_z = (current_pbr - pbr_mean) / pbr_std if (pbr_std and current_pbr) else 0

    out = {
        '_description': f'{stock_name} 5Y PER/PBR 밴드 (FDR 연말종가 + KIS 재무비율 EPS/BPS)',
        'market': 'KR',
        # --- 기존 키 (generate_all #11 / verify_numbers B16 / build_snapshot 호환) ---
        'closes': closes,
        'per_series': [round(x, 4) for x in per_series],
        'pbr_series': [round(x, 4) for x in pbr_series],
        'per_mean': per_mean, 'per_std': per_std,
        'pbr_mean': pbr_mean, 'pbr_std': pbr_std,
        'current_per': current_per, 'current_per_z': current_per_z,
        'current_pbr': current_pbr, 'current_pbr_z': current_pbr_z,
        'current_price': current_price,
        # --- v5.7 가드 (US 판과 동일 스키마) ---
        'excluded_years': excluded_years,
        'skipped_years': built['skipped'],
        'ref_shares': round(ref_shares) if ref_shares else None,
        'detail': built['detail'],
        'per_band_valid': per_valid, 'pbr_band_valid': pbr_valid,
        'warnings': warnings,
    }
    os.makedirs(f'data/{stock_name}', exist_ok=True)
    path = f'data/{stock_name}/_per_band.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    if excluded_years:
        print(f"[NOTE] 진행 중인 당해년도 제외: {excluded_years} (연말 종가가 아직 없다)")
    for y, why in sorted(built['skipped'].items()):
        print(f"[NOTE] {y} 제외 - {why}")
    print(f"[OK] 5Y PER: mean={per_mean:.2f}x, std={per_std:.2f}, "
          f"current={current_per:.2f}x (z={current_per_z:+.2f}σ) valid={per_valid}")
    print(f"[OK] 5Y PBR: mean={pbr_mean:.2f}x, std={pbr_std:.2f}, "
          f"current={current_pbr:.2f}x (z={current_pbr_z:+.2f}σ) valid={pbr_valid}")
    for w in warnings:
        print(f"[WARN] {w}")
    print(f"[OK] saved: {path}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("usage: python scripts/fdr_band.py {종목명} {종목코드}")
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2]))
