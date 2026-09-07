"""
DART 분기 실적 추출 (v5.6 신설)

## 왜 만들었나

두산 리포트에 1Q25 가 빠져 있었고, FnGuide 가 최근 4분기만 주길래
"소급 불가" 로 판단했다. **틀렸다.** DART 는 연도별 분기보고서를 그대로 제공한다.
사용자가 "DART 에서 분기 데이터 못 가지고 오나?" 라고 물어 확인했다.

확인해보니 두산 리포트의 분기 영업이익이 **전부 틀려 있었다**:

    분기     리포트      DART 실측    오차
    1Q25     (누락)      1,985억      --
    2Q25     약 2,500    3,578억      -30%
    3Q25     약 2,700    2,313억      +17%
    4Q25     약 2,500    2,752억      -9%

FnGuide 도 3Q25=2,313 / 4Q25=2,752 로 독립 확인된다.

## DART 금액 컬럼의 의미 (실측으로 확정)

    thstrm_amount      = **당분기 3개월** (standalone)
    thstrm_add_amount  = **누적** (1분기보고서에서는 3개월과 같다)
    사업보고서(11011)  = thstrm_amount 가 **연간 전체**, 누적 컬럼은 비어 있다

따라서 4분기는 직접 공시되지 않고 **연간 - 3분기 누적** 으로 역산한다.
검산: 4개 분기 합 == 연간. 두산 2025 에서 10,627억으로 정확히 일치했다.

## 사용

    python scripts/dart_quarterly.py 두산 2025
    python scripts/dart_quarterly.py 두산 2024 2025        # 여러 해
    python scripts/dart_quarterly.py 두산 2025 --compare   # 리포트와 1:1 대조

출력: data/{종목}/_dart_quarterly.json (억원 단위)

`--compare` 는 v5.4 규칙 19(분기 실측 1:1 대조)를 자동화한다.
"""
import sys
import io
import os
import re
import json
import argparse
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UK = 1e8                      # 원 -> 억원

# 보고서 코드 -> 분기 라벨. 1/2/3분기는 당분기 3개월, 사업보고서는 연간이다.
REPORT_CODES = [('11013', '1Q'), ('11012', '2Q'), ('11014', '3Q'), ('11011', 'FY')]

REV_NAMES = ('매출액', '수익(매출액)', '영업수익', '매출')
OP_NAMES = ('영업이익', '영업이익(손실)')
NI_NAMES = ('당기순이익', '당기순이익(손실)', '분기순이익', '반기순이익',
            '당기순이익(당기순손실)')


def amount(item, key='thstrm_amount'):
    """DART 금액 문자열 -> int. 빈 값/하이픈은 None (0 이 아니다).

    0 을 돌려주면 '값 없음' 이 '실적 0원' 으로 읽혀 조용히 통과한다.
    """
    if not item:
        return None
    v = item.get(key)
    if v is None:
        return None
    s = str(v).replace(',', '').strip()
    if not s or s in ('-', '--'):
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


# 손익 관련 재무제표 구분. 순서가 우선순위다.
#   IS  = 손익계산서
#   CIS = 포괄손익계산서. **많은 회사가 둘을 분리하지 않고 CIS 하나로만 제출한다.**
#         에코프로 실측: IS 0개 / CIS 26개. IS 만 보면 전 계정이 None 이 되어
#         "실적 없음" 으로 조용히 통과한다.
IS_DIVS = ('IS', 'CIS')


def pick_account(items, names):
    """손익 재무제표(IS 우선, 없으면 CIS)에서 계정명이 names 에 있는 첫 항목.

    재무상태표(BS)/현금흐름표(CF)/자본변동표(SCE)의 동명 계정은 제외한다.
    names 는 우선순위 순서다.
    """
    if not items:
        return None
    by_div = {d: {} for d in IS_DIVS}
    for x in items:
        d = x.get('sj_div')
        if d not in by_div:
            continue
        nm = str(x.get('account_nm', '')).strip()
        by_div[d].setdefault(nm, x)
    for div in IS_DIVS:                 # IS 를 CIS 보다 우선 (중복 계상 방지)
        for n in names:
            if n in by_div[div]:
                return by_div[div][n]
    return None


def to_uk(v, nd=2):
    """원 -> 억원."""
    if v is None:
        return None
    return round(v / UK, nd)


def derive_quarters(raw):
    """{'1Q':{rev_q,rev_cum,op_q,op_cum}, ..., 'FY':{...}} -> 분기별 확정값.

    4Q 는 공시되지 않으므로 연간 - 3Q누적 으로 역산한다.
    """
    out = {}
    for q in ('1Q', '2Q', '3Q'):
        d = raw.get(q) or {}
        out[q] = {'rev': d.get('rev_q'), 'op': d.get('op_q'), 'ni': d.get('ni_q'),
                  'source': 'DART 당분기'}

    fy = raw.get('FY') or {}
    q3 = raw.get('3Q') or {}

    def sub(a, b):
        return None if (a is None or b is None) else a - b

    out['4Q'] = {
        'rev': sub(fy.get('rev_q'), q3.get('rev_cum')),
        'op': sub(fy.get('op_q'), q3.get('op_cum')),
        'ni': sub(fy.get('ni_q'), q3.get('ni_cum')),
        'source': '연간 - 3Q누적 (역산)',
    }
    return out


def checksum(quarters, fy, tol_pct=0.5):
    """4개 분기 합이 연간과 맞는지. -> (ok, 설명)"""
    parts = [quarters.get(q, {}).get('op') for q in ('1Q', '2Q', '3Q', '4Q')]
    if any(p is None for p in parts) or fy.get('op_q') is None:
        return False, '영업이익 4개 분기 또는 연간값 결측'
    s = sum(parts)
    annual = fy['op_q']
    if annual == 0:
        return s == 0, '연간 영업이익 0'
    diff = abs(s - annual) / abs(annual) * 100
    ok = diff <= tol_pct
    return ok, (f'분기합 {to_uk(s):,.0f}억 vs 연간 {to_uk(annual):,.0f}억 '
                f'(차이 {diff:.2f}%)')


_NUM = re.compile(r'-?[\d,]+(?:\.\d+)?')
_EST = re.compile(r'(?i)\bE\b|추정|가이던스|예상|전망|컨센|\(E\)')


def compare_with_report(quarters, year, headers, rows, tol_pct=10, metric='영업이익'):
    """v5.4 규칙 19 -- 리포트 분기표와 DART 실측을 1:1 대조.

    추정치 컬럼(E/추정/가이던스)은 대조하지 않는다. 실측만 본다.
    -> [{quarter, reported, actual, diff_pct}]
    """
    if not headers or not rows:
        return []
    row = None
    for k, v in (rows.items() if isinstance(rows, dict) else []):
        if metric in str(k):
            row = v
            break
    if row is None and isinstance(rows, list):
        for r in rows:
            if r and metric in str(r[0]):
                row = r[1:]
                break
    if not row:
        return []

    yy = str(year)[2:]
    diffs = []
    cols = headers[1:] if len(headers) > 1 else []
    for i, col in enumerate(cols):
        if i >= len(row):
            break
        label = str(col)
        if _EST.search(label):
            continue
        m = re.search(r'([1-4])Q\s*(\d{2})', label)
        if not m or m.group(2) != yy:
            continue
        q = f'{m.group(1)}Q'
        actual = to_uk(quarters.get(q, {}).get('op'))
        cell = str(row[i])
        if _EST.search(cell):
            continue
        nums = _NUM.findall(cell.replace(' ', ''))
        if not nums or actual is None or actual == 0:
            continue
        reported = float(nums[0].replace(',', ''))
        diff_pct = (reported - actual) / abs(actual) * 100
        if abs(diff_pct) > tol_pct:
            diffs.append({'quarter': f'{q}{yy}', 'reported': reported,
                          'actual': actual, 'diff_pct': round(diff_pct, 1)})
    return diffs


def fetch_year(corp_code, year):
    """한 해의 분기별 원자료를 모은다. DART 호출 4회."""
    from dart_api import get_consolidated_statements
    raw, errors = {}, []
    for rc, q in REPORT_CODES:
        try:
            items = (get_consolidated_statements(corp_code, str(year), rc) or {}).get('list') or []
        except Exception as e:
            errors.append(f'{year} {q}({rc}) 조회 실패: {type(e).__name__}: {str(e)[:80]}')
            raw[q] = {}
            continue
        if not items:
            errors.append(f'{year} {q}({rc}) 항목 0개 -- 미제출이거나 코드 불일치')
            raw[q] = {}
            continue
        rev, op, ni = (pick_account(items, REV_NAMES),
                       pick_account(items, OP_NAMES),
                       pick_account(items, NI_NAMES))
        if rev is None and op is None:
            from collections import Counter
            divs = Counter(x.get('sj_div') for x in items)
            names = [str(x.get('account_nm', ''))[:20] for x in items
                     if x.get('sj_div') in IS_DIVS][:6]
            errors.append(
                f'{year} {q}({rc}) 항목 {len(items)}개인데 매출/영업이익 계정을 못 찾았다. '
                f'sj_div 분포={dict(divs)} 손익계정 예시={names} '
                f'-- 계정명 별칭(REV_NAMES/OP_NAMES) 추가가 필요하다')
        raw[q] = {
            'rev_q': amount(rev), 'rev_cum': amount(rev, 'thstrm_add_amount'),
            'op_q': amount(op), 'op_cum': amount(op, 'thstrm_add_amount'),
            'ni_q': amount(ni), 'ni_cum': amount(ni, 'thstrm_add_amount'),
        }
    return raw, errors


def main(argv=None):
    p = argparse.ArgumentParser(description='DART 분기 실적 추출')
    p.add_argument('stock', help='종목명 (data/{종목}/ 에 저장)')
    p.add_argument('years', nargs='*', help='연도 (미지정 시 작년)')
    p.add_argument('--compare', action='store_true',
                   help='analysis.json 분기표와 1:1 대조 (v5.4 규칙 19)')
    p.add_argument('--tol', type=float, default=10.0, help='대조 허용 오차 %% (기본 10)')
    a = p.parse_args(argv)

    from dart_api import get_corp_code
    cc = get_corp_code(a.stock)
    corp = cc[0] if isinstance(cc, (list, tuple)) else cc
    if not corp:
        print(f"[ERR] {a.stock} 고유번호 조회 실패")
        return 1

    years = a.years or [str(datetime.now().year - 1)]
    out = {'_description': f'{a.stock} DART 분기 실적 (억원)',
           '_collected_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'stock': a.stock, 'corp_code': corp, 'years': {}, 'warnings': []}

    for y in years:
        raw, errs = fetch_year(corp, y)
        out['warnings'].extend(errs)
        q = derive_quarters(raw)
        ok, detail = checksum(q, raw.get('FY') or {})
        if not ok:
            out['warnings'].append(f'{y} 검산 실패: {detail}')

        out['years'][str(y)] = {
            'quarters': {k: {'revenue': to_uk(v['rev']), 'op_income': to_uk(v['op']),
                             'net_income': to_uk(v['ni']), 'source': v['source']}
                         for k, v in q.items()},
            'annual': {'revenue': to_uk((raw.get('FY') or {}).get('rev_q')),
                       'op_income': to_uk((raw.get('FY') or {}).get('op_q')),
                       'net_income': to_uk((raw.get('FY') or {}).get('ni_q'))},
            'checksum_ok': ok, 'checksum_detail': detail,
        }

        print(f"\n  {a.stock} {y} 분기 실측 (DART 연결, 억원)")
        print(f"    {'분기':<6} {'매출':>12} {'영업이익':>10} {'순이익':>10}  출처")
        def cell(v, w=12):
            # 결측을 0 으로 찍으면 '실적 0원' 으로 오독된다. 명시적으로 비운다.
            return f"{v:>{w},.0f}" if v is not None else f"{'미수집':>{w - 3}}"

        for k in ('1Q', '2Q', '3Q', '4Q'):
            v = q[k]
            print(f"    {k}{str(y)[2:]:<4} {cell(to_uk(v['rev']))} "
                  f"{cell(to_uk(v['op']), 10)} {cell(to_uk(v['ni']), 10)}  {v['source']}")
        fy = raw.get('FY') or {}
        print(f"    {'연간':<6} {cell(to_uk(fy.get('rev_q')))} "
              f"{cell(to_uk(fy.get('op_q')), 10)} {cell(to_uk(fy.get('ni_q')), 10)}")
        print(f"    검산: {'OK' if ok else 'FAIL'} -- {detail}")

        if a.compare:
            ap = f'scripts/analysis_{a.stock}.json'
            if not os.path.exists(ap):
                print(f"    [SKIP] {ap} 없음")
            else:
                d = json.load(open(ap, encoding='utf-8')).get('quarterly') or {}
                diffs = compare_with_report(q, y, d.get('headers'), d.get('rows'), a.tol)
                if diffs:
                    print(f"\n    [불일치 {len(diffs)}건] 리포트 vs DART 실측 (영업이익)")
                    for x in diffs:
                        print(f"      {x['quarter']}  리포트 {x['reported']:>9,.0f} vs "
                              f"실측 {x['actual']:>9,.0f}  ({x['diff_pct']:+.1f}%)")
                    out['warnings'].append(
                        f'{y} 리포트 분기표 불일치 {len(diffs)}건: '
                        + ', '.join(f"{x['quarter']} {x['diff_pct']:+.0f}%" for x in diffs))
                elif not (d.get('headers') and d.get('rows')):
                    print("    [대조 불가] 리포트에 분기표가 없다")
                    out['warnings'].append(f'{y} 리포트에 분기표 없음 -- 대조 불가')
                elif all(v.get('op') is None for v in q.values()):
                    print("    [대조 불가] DART 실측이 비어 있다")
                else:
                    print(f"    [대조 OK] 리포트 분기표가 실측과 {a.tol:.0f}% 이내")

    os.makedirs(f'data/{a.stock}', exist_ok=True)
    path = f'data/{a.stock}/_dart_quarterly.json'
    json.dump(out, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\n[OK] saved: {path}")
    for w in out['warnings']:
        print(f"  [WARN] {w}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
