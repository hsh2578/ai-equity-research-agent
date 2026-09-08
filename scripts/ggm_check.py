"""ggm_check.py -- Target 배수를 자본효율로 정당화한다 (v5.12 규칙 5).

배경(2026-09 수상작 정독): 수상작은 Target 배수의 근거를 자본효율에 건다.

    "Target PBR 1.3배: 18%대 ROIC 가 정당화하는 밴드 상단 소폭 돌파" (에스엘)

우리 리포트는 전부 "업종 평균 대비 13.5% 할인" 같은 **임의 계수**였다.
할인율의 근거가 서술에만 있고 숫자에 없으면 독자가 재현할 수 없다.

Gordon Growth Model 은 장부가 배수를 세 값으로 묶는다.

    PBR = (ROE - g) / (COE - g)          PER = PBR / ROE

이 식이 주는 것은 **정답이 아니라 기준선**이다. Target 이 기준선보다 높으면
그 초과분을 설명해야 하고, 설명하지 못하면 임의 계수와 다를 바 없다.
반대로 기준선보다 낮으면 보수적인 것이므로 추가 설명 부담이 없다.

사용: python scripts/ggm_check.py {종목명} [--target-pbr 2.1] [--roe 0.09]
     인자 없으면 analysis.json + financial_summary 에서 최대한 추정한다.
"""
import io
import json
import os
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DEFAULT_COE = 0.095       # 자본비용 기본 가정 (무위험 + 시장 프리미엄 통상치)
DEFAULT_G = 0.03          # 영구 성장률 기본 가정
PREMIUM_LIMIT = 1.30      # 기준선의 이 배수를 넘으면 초과분을 설명해야 한다
INLINE_BAND = 0.10        # 기준선 ±10% 는 INLINE


def implied_pbr(roe, coe=DEFAULT_COE, g=DEFAULT_G):
    """GGM 기준선 PBR. 성립하지 않는 입력은 **값을 만들지 않는다**(None)."""
    if roe is None or coe is None or g is None:
        return None
    if roe <= 0:
        return None            # 적자면 장부가 배수를 정당화할 수 없다
    if g >= coe:
        return None            # 영구 성장률이 자본비용 이상이면 발산한다
    return (roe - g) / (coe - g)


def implied_per(roe, coe=DEFAULT_COE, g=DEFAULT_G):
    """GGM 기준선 PER = 기준선 PBR / ROE."""
    p = implied_pbr(roe, coe, g)
    if p is None or not roe:
        return None
    return p / roe


HIGH_ROE = 0.15           # 이 위에서는 g=3% 가정이 기준선을 과소평가한다


def justify(target_pbr, roe, coe=DEFAULT_COE, g=DEFAULT_G, normalized_roe=None):
    """Target 배수가 기준선 대비 어디인가.

    normalized_roe 를 주면 그것으로 기준선을 만든다 -- 단년도 ROE(바닥/피크)를
    영구값으로 쓰면 기준선이 왜곡되기 때문이다.

    반환: {'implied_pbr','ratio','verdict','needs_explanation','roe_used','caveat'}
      verdict = DISCOUNT / INLINE / PREMIUM / UNKNOWN
    """
    used = normalized_roe if normalized_roe is not None else roe
    base = implied_pbr(used, coe, g)
    out = {'implied_pbr': base, 'ratio': None, 'verdict': 'UNKNOWN',
           'needs_explanation': False, 'roe_used': used, 'caveat': None}

    # 고ROE 기업은 g=3% 가정이 지속가능성장률보다 훨씬 낮아 기준선이 과소평가된다.
    # 그 상태의 PREMIUM 을 "고평가" 로 읽으면 틀린다.
    if used is not None and used > HIGH_ROE and g <= DEFAULT_G:
        out['caveat'] = (f'ROE {used * 100:.1f}% 는 지속가능성장률(ROE x 유보율)이 '
                         f'가정 g {g * 100:.1f}% 를 크게 웃돈다. 기준선이 과소평가되므로 '
                         f'PREMIUM 판정을 그대로 고평가로 읽지 말 것')
    if base is None or not target_pbr:
        return out
    ratio = target_pbr / base
    out['ratio'] = ratio
    if ratio > 1 + INLINE_BAND:
        out['verdict'] = 'PREMIUM'
    elif ratio < 1 - INLINE_BAND:
        out['verdict'] = 'DISCOUNT'
    else:
        out['verdict'] = 'INLINE'
    out['needs_explanation'] = ratio > PREMIUM_LIMIT
    return out


# ---------------------------------------------------------------- CLI
def _roe_from_analysis(A):
    """지배주주 순이익 / 자기자본(BPS x 주식수). 없으면 None."""
    p = A.get('price') or {}
    bps = p.get('bps')
    sh = p.get('shares_outstanding')
    if not bps or not sh:
        return None, None
    equity = bps * sh / 1e8          # 억원
    fe = p.get('forward_eps')
    if not fe:
        return None, equity
    ni = fe * sh / 1e8               # 억원
    return (ni / equity if equity else None), equity


def main(name, target_pbr=None, roe=None, coe=DEFAULT_COE, g=DEFAULT_G,
         normalized_roe=None):
    norm_roe = normalized_roe
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = os.path.join(root, 'scripts', f'analysis_{name}.json')
    if not os.path.exists(ap):
        print(f'[ERR] {ap} 없음')
        return 1
    with open(ap, encoding='utf-8') as f:
        A = json.load(f)
    p = A.get('price') or {}
    o = A.get('opinion') or {}

    est_roe, equity = _roe_from_analysis(A)
    roe = roe if roe is not None else est_roe
    if target_pbr is None and p.get('bps') and o.get('target_base'):
        target_pbr = o['target_base'] / p['bps']

    print(f'=== {name} Target 배수 정당화 (GGM) ===')
    print(f'  BPS {p.get("bps"):,}원 / 주식수 {p.get("shares_outstanding"):,}주'
          if p.get('bps') and p.get('shares_outstanding') else '  (자본 정보 부족)')
    if equity:
        print(f'  자기자본 추정 {equity:,.0f}억원')
    if roe is None:
        print('  ROE: 미확인 -- 판정 불가. --roe 로 직접 주거나 forward_eps 를 채울 것')
        return 0
    print(f'  ROE(추정) {roe * 100:.1f}%  COE {coe * 100:.1f}%  g {g * 100:.1f}%')
    r = justify(target_pbr, roe, coe, g, normalized_roe=norm_roe)
    print(f'  GGM 기준선 PBR {r["implied_pbr"]:.2f}배 / 기준선 PER '
          f'{(implied_per(roe, coe, g) or 0):.1f}배')
    print(f'  본 리포트 Target PBR {target_pbr:.2f}배 '
          f'(목표주가 {o.get("target_base", 0):,}원 / BPS)')
    print(f'  판정: {r["verdict"]}  (기준선의 {r["ratio"]:.2f}배)')
    if r.get('caveat'):
        print(f'  [caveat] {r["caveat"]}')
    if r['needs_explanation']:
        print(f'  [주의] 기준선의 {PREMIUM_LIMIT}배를 넘는다 -- '
              f'본문에 초과분의 근거를 반드시 쓸 것')
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    args = sys.argv[1:]
    name = args[0]
    kw = {}
    for i, a in enumerate(args):
        if a == '--target-pbr':
            kw['target_pbr'] = float(args[i + 1])
        elif a == '--roe':
            kw['roe'] = float(args[i + 1])
        elif a == '--coe':
            kw['coe'] = float(args[i + 1])
        elif a == '--g':
            kw['g'] = float(args[i + 1])
        elif a == '--normalized-roe':
            kw['normalized_roe'] = float(args[i + 1])
    raise SystemExit(main(name, **kw))
