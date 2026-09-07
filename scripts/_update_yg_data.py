"""YG analysis_와이지엔터.json 데이터 새로고침 (2026-06-03 기준).
KIS 실측 + FnGuide 컨센 + Peer 4사 KIS 일괄 -> price/peers/supply/forward + 본문 수치 치환.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PATH = 'scripts/analysis_와이지엔터.json'
kis = json.load(open('data/와이지엔터테인먼트/_kis_fresh.json', encoding='utf-8'))
fng = json.load(open('data/와이지엔터테인먼트/_fnguide_fresh.json', encoding='utf-8'))
peers = json.load(open('data/와이지엔터테인먼트/_peers_fresh.json', encoding='utf-8'))

A = json.load(open(PATH, encoding='utf-8'))
p = kis['price']
trend = kis['trend']
returns = kis['returns']

# ===== meta =====
A['meta']['date'] = '2026-06-03'
A['meta']['version'] = 'v6.1 -- 2026-06-03 데이터 새로고침 (KIS 실측 + FnGuide 컨센)'

# ===== price =====
cur = int(p['현재가'])
fwd_eps = int(fng['consensus']['eps'].get('2026/12(E)', 3072))
fwd_per = round(cur / fwd_eps, 2)
mc_eok = int(p['시가총액'])
A['price'].update({
    'current': cur,
    'change_pct': float(p['등락률']),
    'high_52w': int(p['52주최고']),
    'low_52w': int(p['52주최저']),
    'market_cap': f'{mc_eok/10000:.2f}조',
    'market_cap_num': mc_eok,
    'per': float(p['PER']),
    'pbr': float(p['PBR']),
    'eps': int(p['EPS']),
    'bps': int(p['BPS']),
    'forward_per': fwd_per,
    'forward_eps': fwd_eps,
    'vol_annual_pct': kis['sigma_annual_pct'],
    'returns_3m_pct': returns['3m'],
    'returns_6m_pct': returns['5m'],   # ~5개월 (KIS 100일 한계)
    'returns_1m_pct': returns['1m'],
})

# ===== opinion R/R 산수 갱신 (target 자체는 분석가 결정이라 그대로) =====
op = A['opinion']
base = op['target_base']; bull = op['target_bull']; bear = op['target_bear']
up_base = round((base - cur)/cur*100, 1)
dn_bear = round((bear - cur)/cur*100, 1)
rr_base = round((base - cur)/max(1, cur - bear), 1)
rr_bull = round((bull - cur)/max(1, cur - bear), 1)
op['risk_reward'] = (f'1:{rr_base} (Base) / 1:{rr_bull} (Bull) -- 현재가 {cur:,}원 / Bear {bear:,}원 기준. '
                    f'상방(Base) +{up_base}% vs 하방(Bear) {dn_bear:+}%')

# ===== supply (20일, 주식수) =====
A['supply'].update({
    'foreign': int(trend.get('외국인_순매수', 0)),
    'institution': int(trend.get('기관_순매수', 0)),
    'individual': int(trend.get('개인_순매수', 0)),
    'days': 20,
    'comment': '5/19 대비 외국인 매도→매수 반전(+17.4만주), 기관 매도세 지속(-31.2만주), 개인은 매수 폭 축소(+13.9만주). 6월 초 기준 -32.6% 추가 하락(3M) 와중에도 외인 순매수 전환은 단기 바닥 신호 가능.'
})

# ===== peers 4사 (KIS 실측) =====
def shorten(n):
    return {'와이지엔터테인먼트':'와이지엔터테인먼트 (본 종목)', '하이브':'하이브 (HYBE)',
            'JYP Ent.':'JYP Ent.', '에스엠':'에스엠 (SM)'}.get(n, n)
peer_list = []
for n, d in peers.items():
    per = d['per']; pbr = d['pbr']
    mc = d['market_cap_억']
    note = ''
    if n == '와이지엔터테인먼트':
        note = f"5종 IP·순현금 2,737억, 6/3 PER {per:.1f}배"
        hl = True
    elif n == '하이브':
        note = 'BTS 위주, 1Q 적자(PER 음수)'
        hl = False
    elif n == 'JYP Ent.':
        note = '엔믹스·스키즈 중심, PER 12.3배'
        hl = False
    else:  # SM
        note = 'NCT·에스파, PER 5.2배(저평가)'
        hl = False
    peer_list.append({
        'name': shorten(n),
        'market_cap': f'{mc/10000:.2f}조' if mc >= 10000 else f'{mc/1000:.1f}천억',
        'per': per, 'pbr': pbr, 'note': note, 'highlight': hl,
    })
A['peers'] = peer_list

# ===== 본문 수치 토큰 치환 =====
old_new = [
    ('48,050원', f'{cur:,}원'), ('48,050', f'{cur:,}'),
    ('0.90조', f'{mc_eok/10000:.2f}조'),
    ('8,981억', f'{mc_eok:,}억'), ('8,981', f'{mc_eok:,}'),
    ('Forward PER 15.9', f'Forward PER {fwd_per}'),
    ('12MF PER 15.9', f'12MF PER {fwd_per}'),
    ('15.9배', f'{fwd_per}배'), ('15.9 배', f'{fwd_per}배'),
    ('24.34', f'{float(p["PER"]):.2f}'),
    ('-26.8%', f'{returns["3m"]:.1f}%'), ('-26.82', f'{returns["3m"]}'),
    ('-3.8/-26.8/-24.2', f'{returns["1m"]:.1f}/{returns["3m"]:.1f}/N/A'),
    ('현재가 48,050', f'현재가 {cur:,}'),
]
n_subst = 0
for skey, content in A.get('sections', {}).items():
    if not isinstance(content, str): continue
    new = content
    for a, b in old_new:
        if a in new:
            new = new.replace(a, b)
            n_subst += new.count(b) - content.count(b)
    if new != content:
        A['sections'][skey] = new
        n_subst += 1

json.dump(A, open(PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print(f'analysis 갱신 완료: {PATH}')
print(f'  현재가 {cur:,}원 / 시총 {mc_eok:,}억 / PER {p["PER"]} / PBR {p["PBR"]} / Forward PER {fwd_per}')
print(f'  3M 수익률 {returns["3m"]}% / σ {kis["sigma_annual_pct"]}% / 52w최저 {p["52주최저"]:,}원')
print(f'  외국인 매수 전환 +{int(trend["외국인_순매수"]):,}주 (20일)')
print(f'  Peer 4사 새로고침, 본문 토큰 치환 ≈ {n_subst}회')
