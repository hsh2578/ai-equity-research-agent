"""
검증된 수치 스냅샷 생성 (v5.5 신설) -- 사전 그라운딩(pre-hoc grounding)

배경
----
지금까지 우리 파이프라인은 **사후 검증**이었다. 리포트를 다 쓴 뒤 verify_numbers.py
B1~B19 로 틀린 숫자를 적발했다. 그런데 반복 사고(JYP Peer 전부 0, 삼성전자 301조 거절,
풍산 '17개사 162,500원' 추정, 한미반도체 4Q25 미인지)는 전부 같은 유형이다:
**권위 있는 단일 진실 테이블이 없어서 빈칸을 상상으로 메운 것.**

TradingAgents 의 market_data_validator.py 는 반대로 간다. 작성 **전에** 결정론적
진실 테이블을 만들어 프롬프트에 넣고 이렇게 못박는다:

    "이 스냅샷을 모든 정확한 수치 주장의 source of truth 로 삼아라.
     다른 도구 출력이 충돌하면 화해시킨 숫자를 만들지 말고 불일치를 보고하라.
     구체적 날짜와 가격이 도구 출력에 직접 뒷받침되지 않는 한
     역사적 검증/지지선 반등/정확한 % 변동을 주장하지 마라."

이 스크립트는 이미 흩어져 있는 실측 파일들을 한 장의 마크다운으로 묶는다.
새 데이터를 수집하지 않는다. **없는 것은 '미수집' 으로 명시**하는 것이 핵심이다 --
빈칸이 어디인지 알아야 상상으로 메우지 않는다.

사용법
------
    python scripts/build_snapshot.py 한국콜마      # KR (자동 감지)
    python scripts/build_snapshot.py AMD           # US (자동 감지)

출력: data/{종목}/_verified_snapshot.md
STEP 3(심층 분석) 진입 전 이 파일을 Read 하는 것이 의무다.
"""
import sys
import io
import os
import json
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MISSING = '미수집'


def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def fmt(v, unit='', nd=2, comma=True):
    """숫자를 표에 넣을 문자열로. None 이면 명시적으로 '미수집'."""
    if v is None or v == '':
        return MISSING
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if comma and abs(f) >= 1000:
        s = f"{f:,.0f}"
    elif f == int(f) and abs(f) < 1000:
        s = f"{int(f)}"
    else:
        s = f"{f:,.{nd}f}"
    return f"{s}{unit}"


def _first(d, *keys, default=None):
    """여러 스키마 변종 중 처음 값이 있는 키를 고른다.

    수집 스크립트마다 키 이름이 갈려 있다 (peer_snapshot.py 는 code/market_cap_uk,
    구 산출물은 종목코드/시가총액). 한쪽만 보면 있는 데이터가 '미수집' 으로 렌더되고,
    그러면 에이전트가 실제로 있는 데이터를 없다고 결론 낸다.
    """
    if not isinstance(d, dict):
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, ''):
            return v
    return default


def vol_annual_pct(beta: dict):
    """연율 변동성을 **% 단위**로 통일해 돌려준다. 없으면 None.

    volatility_beta.py(KR)  -> vol_annual = 0.4525  (비율)
    US 인라인 산출물         -> vol_annual_pct = 62.33 (이미 %)
    과거 산출물              -> sigma_annual = 38.4   (%)

    과거 코드는 `sigma_annual` / `변동성` 만 봐서 KR/US 실측 파일 어느 쪽도
    읽지 못하고 항상 '미수집' 을 냈다.
    """
    if not isinstance(beta, dict):
        return None
    v = _first(beta, 'vol_annual_pct', 'sigma_annual_pct', '연율변동성_pct')
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    v = _first(beta, 'vol_annual', 'sigma_annual', '변동성', 'volatility')
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    # 비율(0.45)로 저장된 값과 %(45.2)로 저장된 값이 섞여 있다.
    # 연율 변동성이 300% 를 넘는 주식은 사실상 없으므로 3.0 을 경계로 쓴다.
    return f * 100 if abs(f) <= 3.0 else f


class Snapshot:
    def __init__(self, name):
        self.name = name
        self.dir = f'data/{name}'
        self.lines = []
        self.gaps = []          # 미수집 항목 -> 리포트에서 주장 금지 목록
        self.kis = load(f'{self.dir}/data_kis.json')
        self.kis_us = load(f'{self.dir}/data_kis_us.json')
        self.fs = load(f'{self.dir}/financial_summary.json')
        self.band = load(f'{self.dir}/_per_band.json')
        self.peer = load(f'{self.dir}/_peer_snapshot.json')
        self.beta = load(f'{self.dir}/_volatility_beta.json')
        self.fng = load(f'{self.dir}/_fnguide.json')
        self.cons_us = load(f'{self.dir}/_us_consensus.json')
        self.market = 'US' if (self.kis_us or self.cons_us) and not self.kis else 'KR'
        self.cur = '$' if self.market == 'US' else '원'

    # ---------- 렌더 헬퍼 ----------
    def h(self, text, level=2):
        self.lines.append(f"\n{'#' * level} {text}\n")

    def p(self, text):
        self.lines.append(text)

    def table(self, headers, rows):
        self.lines.append('| ' + ' | '.join(headers) + ' |')
        self.lines.append('|' + '|'.join(['---'] * len(headers)) + '|')
        for r in rows:
            self.lines.append('| ' + ' | '.join(str(c) for c in r) + ' |')
        self.lines.append('')

    def gap(self, item, consequence):
        self.gaps.append((item, consequence))

    # ---------- 섹션 ----------
    def sec_price(self):
        self.h('1. 시세 / 밸류에이션 (수집 시점 실측)')
        rows = []
        if self.market == 'KR':
            # data_kis.json 은 한글 키, financial_summary.json['kis'] 는 영문 키를 쓴다.
            # 둘 중 하나만 보면 전 항목이 None 이 되므로 반드시 병합한다.
            raw = (self.kis or {}).get('current_price') or {}
            k = (self.fs or {}).get('kis') or {}

            def pick(ko, en):
                v = raw.get(ko)
                return v if v not in (None, '') else k.get(en)

            pairs = [('현재가', pick('현재가', 'current_price'), self.cur),
                     ('시가총액', pick('시가총액', 'market_cap_억'), '억원'),
                     ('PER(TTM)', pick('PER', 'per'), '배'),
                     ('PBR', pick('PBR', 'pbr'), '배'),
                     ('EPS', pick('EPS', 'eps'), self.cur),
                     ('BPS', pick('BPS', 'bps'), self.cur),
                     ('52주 최고', pick('52주최고', 'high_52w'), self.cur),
                     ('52주 최저', pick('52주최저', 'low_52w'), self.cur)]
            # EPS 교차검증 실패는 리포트 EPS 서술의 신뢰도를 직접 깎으므로 노출한다.
            ev = k.get('eps_validation') or {}
            if ev and ev.get('ok') is False:
                self.p(f"> **[EPS 교차검증 실패]** 시세 API EPS {fmt(ev.get('price_api_eps'))} vs "
                       f"재무 API EPS {fmt(ev.get('finance_api_eps'))} (차이 {fmt(ev.get('diff_pct'), '%', 1)}). "
                       f"EPS 를 인용할 때 어느 기준인지 반드시 명시할 것.\n")
        else:
            yf = (self.fs or {}).get('yfinance') or {}
            self_peer = {}
            if self.peer:
                for v in self.peer.values():
                    if isinstance(v, dict) and v.get('ticker') == self.name.upper():
                        self_peer = v
                        break
            pairs = [('현재가', self_peer.get('price') or yf.get('price'), ''),
                     ('시가총액($B)', self_peer.get('market_cap_b'), 'B'),
                     ('PER(TTM)', self_peer.get('per_trailing'), '배'),
                     ('Forward PER', self_peer.get('per_forward'), '배'),
                     ('PBR', self_peer.get('pbr'), '배'),
                     ('EV/EBITDA', self_peer.get('ev_ebitda'), '배'),
                     ('52주 최고', self_peer.get('high_52w'), ''),
                     ('52주 최저', self_peer.get('low_52w'), '')]
        for label, val, unit in pairs:
            rows.append([label, fmt(val, unit)])
            if val in (None, 0):
                self.gap(label, f'{label} 수치 인용 금지')
        self.table(['항목', '실측값'], rows)

    def sec_financials(self):
        self.h('2. 연간 실적 (확정치 -- 추정치와 절대 혼용 금지)')
        fins = (self.fs or {}).get('financials') or {}
        if not fins:
            self.p(f'**{MISSING}** -- financial_summary 미실행. 연간 실적 수치 인용 금지.')
            self.gap('연간 실적', '매출/영업이익/순이익/EPS 시계열 인용 금지')
            return
        years = sorted(y for y in fins if str(y).isdigit())
        unit = '($)' if self.market == 'US' else '(억원)'
        div = 1e8 if self.market == 'KR' else 1e9
        ulab = '억원' if self.market == 'KR' else '$B'
        rows = []
        for key, label in [('revenue', f'매출({ulab})'), ('op_income', f'영업이익({ulab})'),
                           ('net_income', f'순이익({ulab})'), ('eps', 'EPS'), ('opm', 'OPM(%)')]:
            row = [label]
            for y in years:
                v = fins[y].get(key)
                if key in ('revenue', 'op_income', 'net_income') and v is not None:
                    v = float(v) / div
                    row.append(fmt(v, '', 0 if self.market == 'KR' else 1))
                else:
                    row.append(fmt(v))
            rows.append(row)
        self.table(['항목'] + years, rows)
        self.p(f'> 위 연도는 **확정 실적**이다. 2026E 등 추정 연도를 이 표에 섞지 말 것.')

    def sec_quarterly(self):
        self.h('3. 분기 실측')
        fng_fin = (self.fng or {}).get('financial') or {}
        q = ((self.fs or {}).get('quarterly')
             or (fng_fin.get('quarter') if isinstance(fng_fin, dict) else None))
        if not q:
            self.p(f'**{MISSING}** -- 분기 실측 없음. QoQ/사이클 전환 주장 금지.')
            self.gap('분기 실측', 'QoQ 증감, 사이클 전환, 분기 OPM 압축 주장 금지')
            return
        self.p('```json')
        self.p(json.dumps(q, ensure_ascii=False, indent=2)[:1800])
        self.p('```')

    def sec_consensus(self):
        self.h('4. 컨센서스 (본문의 Forward 수치는 반드시 여기서 나와야 한다)')
        if self.market == 'KR':
            fng_fin = (self.fng or {}).get('financial') or {}
            est = ((self.fng or {}).get('consensus')
                   or (fng_fin.get('estimate') if isinstance(fng_fin, dict) else None)
                   or (self.fs or {}).get('consensus')
                   or (self.fs or {}).get('consensus_year'))
            if not est:
                self.p(f'**{MISSING}** -- FnGuide 컨센 미수집. Forward PER/EPS, 목표주가 인용 금지.')
                self.gap('컨센서스', 'Forward PER/EPS, "시장 기대", 목표주가 컨센 인용 금지')
                return
            self.p('```json')
            self.p(json.dumps(est, ensure_ascii=False, indent=2)[:1800])
            self.p('```')
        else:
            if not self.cons_us:
                self.p(f'**{MISSING}** -- us_consensus.py 미실행. '
                       f'컨센 추이/리비전/목표가 인용 금지.')
                self.gap('컨센서스', '컨센 상향/하향, Forward EPS, 목표가 인용 금지')
                return
            dv = self.cons_us.get('derived', {})
            est = self.cons_us.get('eps_estimate', {})
            rows = []
            for k, lab in [('0q', '당분기'), ('+1q', '다음분기'), ('0y', '당해년도'), ('+1y', '내년')]:
                r = est.get(k) or {}
                rows.append([lab, fmt(r.get('avg')), fmt(r.get('low')), fmt(r.get('high')),
                             fmt(r.get('numberOfAnalysts'), '명', 0)])
            self.table(['기간', 'EPS 평균', '최저', '최고', '분석가'], rows)

            tr = self.cons_us.get('eps_trend', {})
            rows = []
            for k, lab in [('0y', '당해년도'), ('+1y', '내년')]:
                r = tr.get(k) or {}
                rows.append([lab, fmt(r.get('current')), fmt(r.get('30daysAgo')),
                             fmt(r.get('90daysAgo')),
                             fmt(dv.get(f'revision_{k}_90d_pct'), '%', 1),
                             fmt(dv.get(f'net_revisions_{k}_30d'), '건', 0)])
            self.table(['기간', '현재', '30일전', '90일전', '90일 변화', '순리비전30d'], rows)
            self.p(f"**컨센 방향 판정: {dv.get('consensus_direction', MISSING)}** "
                   f"-- 본문이 이와 반대로 서술하면 B11 이 FAIL 을 낸다.\n")
            pt = self.cons_us.get('price_targets', {})
            if pt:
                self.p(f"목표가: 평균 {fmt(pt.get('mean'))} / 최저 {fmt(pt.get('low'))} / "
                       f"최고 {fmt(pt.get('high'))}\n")

    def sec_band(self):
        self.h('5. 밸류에이션 밴드 (유효성 게이트 주의)')
        if not self.band:
            self.p(f'**{MISSING}** -- 밴드 미산출. "5년 평균 대비", z-score, 밴드 상/하단 표현 금지.')
            self.gap('밸류 밴드', '"역사적 고평가/저평가", z-score, 밴드 표현 금지')
            return
        b = self.band
        valid = b.get('per_band_valid')
        rows = [['PER', fmt(b.get('per_mean')), fmt(b.get('per_std')),
                 fmt(b.get('current_per')), fmt(b.get('current_per_z'), 'σ'),
                 str(valid) if valid is not None else '구버전'],
                ['PBR', fmt(b.get('pbr_mean')), fmt(b.get('pbr_std')),
                 fmt(b.get('current_pbr')), fmt(b.get('current_pbr_z'), 'σ'),
                 str(b.get('pbr_band_valid')) if b.get('pbr_band_valid') is not None else '구버전']]
        self.table(['지표', '5Y 평균', '표준편차', '현재', 'z-score', '밴드 유효'], rows)
        for w in b.get('warnings', []):
            self.p(f'> **[밴드 경고]** {w}\n')
        if valid is False:
            self.gap('밴드 해석', '"5년 평균 대비 저평가/고평가" 단정 금지. 연도별 값을 직접 제시할 것')

    def sec_peer(self):
        self.h('6. Peer 실측 (이 표와 다른 Peer 수치를 쓰면 generate_all 검증 #10 이 차단)')
        if not self.peer:
            self.p(f'**{MISSING}** -- Peer 스냅샷 없음. Peer 시총/PER 비교 서술 금지.')
            self.gap('Peer', 'Peer 시총/PER/PBR 비교, "업종 최저 PER" 류 표현 금지')
            return
        rows = []
        for k, v in self.peer.items():
            if not isinstance(v, dict) or 'error' in v:
                continue
            if self.market == 'US':
                rows.append([k, v.get('ticker', ''), fmt(v.get('market_cap_b'), 'B'),
                             fmt(v.get('per_trailing')), fmt(v.get('per_forward')), fmt(v.get('pbr'))])
            else:
                # peer_snapshot.py 는 code / market_cap_uk(억원) / per / pbr 로 쓴다.
                # 과거에는 '종목코드' / '시가총액' 만 봐서 **수집된 KR Peer 가 전부
                # '미수집' 으로 렌더**됐다 (조용한 무력화). 구 한글 키도 함께 받는다.
                rows.append([k,
                             _first(v, 'code', '종목코드', 'ticker'),
                             fmt(_first(v, 'market_cap_uk', '시가총액', 'market_cap')),
                             fmt(_first(v, 'per', 'PER')),
                             fmt(_first(v, 'pbr', 'PBR')), ''])
        hdr = (['종목', '티커', '시총($B)', 'PER', 'Fwd PER', 'PBR'] if self.market == 'US'
               else ['종목', '코드', '시총(억)', 'PER', 'PBR', ''])
        self.table(hdr, rows)

    def sec_risk(self):
        self.h('7. 변동성 / 베타')
        if not self.beta:
            self.p(f'**{MISSING}** -- volatility_beta 미실행. 베타/변동성 기반 포지션 사이징 주장 금지.')
            self.gap('베타', '베타, 연율 변동성, 시장 민감도 수치 인용 금지')
            return
        b = self.beta
        vol = vol_annual_pct(b)
        beta_v = _first(b, 'beta', '베타')
        r2 = _first(b, 'r_squared', 'r2', 'R2')
        bench = _first(b, 'benchmark', 'market_code', '기준', '기준지수', default=MISSING)
        self.table(['항목', '실측값'],
                   [['Beta', fmt(beta_v)],
                    ['연율 변동성', fmt(vol, '%', 2)],
                    ['R^2', fmt(r2)],
                    ['기준 지수', bench]])
        # 개별 항목이 비어 있으면 그 항목만 '주장 금지' 목록에 올린다.
        # (전체 파일 부재만 gap 으로 잡던 과거에는 변동성이 늘 미수집인데도 gap 이 0 이었다)
        if beta_v is None:
            self.gap('베타', '베타, 시장 민감도 수치 인용 금지')
        if vol is None:
            self.gap('연율 변동성', '연율 변동성, 변동성 기반 포지션 사이징 주장 금지')

    def sec_supply(self):
        if self.market != 'KR':
            return
        self.h('8. 수급 (단위: 주식수 -- 원 단위로 읽으면 서사가 10배 왜곡된다)')
        sup = (self.fs or {}).get('supply') or (self.kis or {}).get('investor_trend')
        if not sup:
            self.p(f'**{MISSING}** -- 수급 미수집. 외국인/기관 순매수 서술 금지.')
            self.gap('수급', '외국인/기관 순매수 규모 서술 금지')
            return
        self.p('```json')
        self.p(json.dumps({k: v for k, v in sup.items() if k != 'detail'},
                          ensure_ascii=False, indent=2)[:900])
        self.p('```')
        self.p('> 거래대금 환산 = 순매수 주식수 x 현재가. 주식수를 원으로 직접 읽지 말 것.\n')

    def sec_rules(self):
        self.h('사용 규칙 (이 스냅샷의 지위)')
        self.p(
            "1. **이 스냅샷이 모든 정확한 수치 주장의 유일한 출처(source of truth)다.**\n"
            "2. 다른 도구 출력이나 웹 검색 결과가 이 표와 충돌하면, "
            "**임의로 화해시킨 숫자를 만들지 말고 불일치 자체를 리포트에 명시**한다.\n"
            "3. 구체적 날짜와 수치가 위 표에 직접 뒷받침되지 않는 한 "
            "**역사적 검증 / 지지선 반등 / 정확한 % 변동 / '역대 최대' 류 주장을 하지 않는다.**\n"
            "4. 위에 `미수집` 으로 표기된 항목은 **그 항목에 대한 수치 주장 자체가 금지**된다. "
            "추정으로 메우지 말고, 필요하면 해당 수집 스크립트를 먼저 실행한다.\n"
            "5. 확정 실적과 추정치(E)는 같은 표에 섞지 않는다.\n")

        if self.gaps:
            self.h('작성 금지 목록 (미수집으로 인한 제약)', 3)
            self.table(['미수집 항목', '금지되는 주장'], self.gaps)
        else:
            self.p('\n> 미수집 항목 없음 -- 전 항목 실측 기반 서술 가능.\n')

    def build(self):
        self.lines = [
            f"# 검증된 수치 스냅샷 -- {self.name}",
            "",
            f"- 시장: **{self.market}**",
            f"- 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 생성기: `scripts/build_snapshot.py` (결정론적, LLM 미개입)",
            "",
            "> 이 파일은 새 데이터를 수집하지 않는다. 이미 수집된 실측 파일을 한 장으로 묶은 것이다.",
        ]
        self.sec_price()
        self.sec_financials()
        self.sec_quarterly()
        self.sec_consensus()
        self.sec_band()
        self.sec_peer()
        self.sec_risk()
        self.sec_supply()
        self.sec_rules()
        return '\n'.join(self.lines)


def main(name):
    if not os.path.isdir(f'data/{name}'):
        print(f"[ERR] data/{name} 없음. STEP 1 데이터 수집 먼저.")
        return 1
    s = Snapshot(name)
    text = s.build()
    path = f'data/{name}/_verified_snapshot.md'
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"[OK] {s.market} 스냅샷 생성: {path}")
    print(f"  섹션 8개 / 미수집 {len(s.gaps)}건")
    for item, cons in s.gaps:
        print(f"    [GAP] {item}: {cons}")
    if len(s.gaps) >= 4:
        print(f"\n  [WARN] 미수집 {len(s.gaps)}건 -- 데이터 수집을 먼저 보완할 것을 권고.")
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python scripts/build_snapshot.py {종목명 또는 TICKER}")
        sys.exit(1)
    sys.exit(main(sys.argv[1]))
