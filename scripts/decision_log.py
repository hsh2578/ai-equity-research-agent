"""
결정 로그 + 사후 반성 (v5.5 신설)

배경
----
output/ 에 리포트 46종이 쌓였는데 **"그 콜이 맞았나" 를 기록한 파일이 0개**였다.
research.md v5.0 규칙 7 이 STEP 8(분기 재방문)을 설계했지만 scripts/quarterly_review.py
는 끝내 만들어지지 않았다. 이 모듈이 그 부채를 갚는다.

설계는 TradingAgents(TauricResearch) 의 agents/utils/memory.py + graph/reflection.py
를 우리 맥락에 맞춰 옮긴 것이다. 핵심 4가지를 그대로 가져왔다:

1. **raw 수익률이 아니라 alpha (벤치마크 대비)** 를 성적으로 쓴다.
   "장이 좋아서 오른 것" 과 "내 논거가 맞아서 오른 것" 을 분리해야 교훈이 남는다.
2. **point-in-time 필터(as_of)**: 과거 시점 재작성/백테스트 시 아직 일어나지 않은
   결과를 학습하는 look-ahead 오염을 막는다.
3. **같은 종목 n건 전문 + 타 종목 최근 교훈 n건 요약** 만 주입한다 (컨텍스트 폭발 방지).
4. **temp 파일 + os.replace 원자적 쓰기**. 쓰다 죽어도 로그 전체가 날아가지 않는다.
   (프로젝트의 _build_{종목}.py 원자 dump 컨벤션과 동일 사상)

로그 형식 (append-only 마크다운)
--------------------------------
    [2026-05-15 | 와이지엔터 | BUY | pending]

    DECISION:
    ...투자 논지 + 목표가...

    <!-- ENTRY_END -->

정산 후:

    [2026-05-15 | 와이지엔터 | BUY | +18.2% | +11.4% | 90d | resolved:2026-08-13]

    DECISION:
    ...

    REFLECTION:
    방향성 적중. 다만 신인 데뷔가 아니라 일본 공연 매출이 견인했다. ...

CLI
---
    python scripts/decision_log.py record 와이지엔터        # analysis.json 읽어 pending 기록
    python scripts/decision_log.py settle 와이지엔터 --note "..."   # 수익률/alpha 계산 후 정산
    python scripts/decision_log.py pending                  # 정산 대기 목록
    python scripts/decision_log.py context 와이지엔터        # 프롬프트 주입용 과거 맥락
    python scripts/decision_log.py stats                    # 적중률 요약
"""
import sys
import io
import os
import re
import json
from datetime import datetime, date

# 이미 UTF-8 로 감싸져 있으면 다시 감싸지 않는다.
# 두 번 감싸면 먼저 만든 래퍼가 GC 될 때 buffer 를 닫아버려
# 이 모듈을 import 한 쪽(테스트 등)의 stdout 이 죽는다.
if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DEFAULT_LOG = 'output/_decision_log.md'
SEPARATOR = "\n\n<!-- ENTRY_END -->\n\n"   # LLM 산문에 등장할 수 없는 하드 구분자

_DECISION_RE = re.compile(r"DECISION:\n(.*?)(?=\nREFLECTION:|\Z)", re.DOTALL)
_REFLECTION_RE = re.compile(r"REFLECTION:\n(.*?)$", re.DOTALL)


# HOLD 를 alpha 부호로만 채점하면 의미가 뒤집힌다.
# HOLD 는 "크게 움직이지 않는다" 는 주장이므로, 크게 움직였으면 틀린 것이다.
# (한국콜마 HOLD 후 alpha -12.8% 는 '하락 적중' 이 아니라 'SELL 을 냈어야 했다' 는 뜻)
HOLD_BAND = 10.0   # |alpha| 가 이 % 안이면 HOLD 적중

_BULLISH = {'BUY', 'STRONG BUY', 'OVERWEIGHT', '매수', '적극매수', '비중확대'}
_BEARISH = {'SELL', 'STRONG SELL', 'UNDERWEIGHT', '매도', '비중축소'}


def score(rating, alpha_pct):
    """등급 방향을 반영한 적중 판정. -> 'HIT' / 'MISS' / 'N/A'"""
    if alpha_pct is None:
        return 'N/A'
    r = (rating or '').upper().strip()
    base = r.split()[0] if r else ''
    if r in _BULLISH or base in _BULLISH:
        return 'HIT' if alpha_pct > 0 else 'MISS'
    if r in _BEARISH or base in _BEARISH:
        return 'HIT' if alpha_pct < 0 else 'MISS'
    if 'HOLD' in r or '중립' in r or '보유' in r:
        return 'HIT' if abs(alpha_pct) <= HOLD_BAND else 'MISS'
    return 'N/A'


class DecisionLog:
    def __init__(self, path=DEFAULT_LOG, max_entries=None):
        self.path = path
        self.max_entries = max_entries
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)

    # ---------------- 쓰기 ----------------
    def store_decision(self, name, trade_date, rating, thesis='', targets=None,
                       price=None, market='KR', extra=''):
        """발간 시점에 pending 항목을 남긴다. LLM 호출 없음."""
        if os.path.exists(self.path):
            raw = open(self.path, encoding='utf-8').read()
            for line in raw.splitlines():
                if line.startswith(f"[{trade_date} | {name} |"):
                    return False        # 멱등: 같은 날짜+종목은 한 번만
        body = [f"발간가: {price} ({market})" if price is not None else f"시장: {market}"]
        if targets:
            body.append("목표가: " + " / ".join(
                f"{k} {v:,}" if isinstance(v, (int, float)) else f"{k} {v}"
                for k, v in targets.items()))
        if thesis:
            body.append(f"투자 논지: {thesis}")
        if extra:
            body.append(extra)
        entry = (f"[{trade_date} | {name} | {rating} | pending]\n\n"
                 f"DECISION:\n" + "\n".join(body) + SEPARATOR)
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return True

    def update_with_outcome(self, name, trade_date, raw_return, alpha_return,
                            holding_days, reflection='', resolution_date=None):
        """pending 을 정산 상태로 바꾸고 REFLECTION 을 덧붙인다. 원자적 쓰기."""
        if not os.path.exists(self.path):
            return False
        text = open(self.path, encoding='utf-8').read()
        blocks = text.split(SEPARATOR)
        prefix = f"[{trade_date} | {name} |"
        updated, new_blocks = False, []
        for block in blocks:
            s = block.strip()
            if not s:
                new_blocks.append(block)
                continue
            lines = s.splitlines()
            tag = lines[0].strip()
            if not updated and tag.startswith(prefix) and tag.endswith("| pending]"):
                fields = [f.strip() for f in tag[1:-1].split("|")]
                rating = fields[2]
                new_tag = (f"[{trade_date} | {name} | {rating} | "
                           f"{raw_return:+.1%} | {alpha_return:+.1%} | {holding_days}d")
                if resolution_date:
                    new_tag += f" | resolved:{resolution_date}"
                new_tag += "]"
                rest = "\n".join(lines[1:]).lstrip()
                refl = reflection.strip() or "(reflection 미작성)"
                new_blocks.append(f"{new_tag}\n\n{rest}\n\nREFLECTION:\n{refl}")
                updated = True
            else:
                new_blocks.append(block)
        if not updated:
            return False
        new_blocks = self._rotate(new_blocks)
        tmp = self.path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(SEPARATOR.join(new_blocks))
        os.replace(tmp, self.path)
        return True

    def _rotate(self, blocks):
        if not self.max_entries or self.max_entries <= 0:
            return blocks
        marks = []
        for b in blocks:
            s = b.strip()
            if not s:
                marks.append((b, False))
                continue
            tag = s.splitlines()[0].strip()
            resolved = tag.startswith('[') and tag.endswith(']') and not tag.endswith('| pending]')
            marks.append((b, resolved))
        n_res = sum(1 for _, r in marks if r)
        drop = n_res - self.max_entries
        if drop <= 0:
            return blocks
        kept = []
        for b, r in marks:
            if r and drop > 0:
                drop -= 1
                continue
            kept.append(b)
        return kept

    # ---------------- 읽기 ----------------
    def load_entries(self):
        if not os.path.exists(self.path):
            return []
        text = open(self.path, encoding='utf-8').read()
        out = []
        for raw in [e.strip() for e in text.split(SEPARATOR) if e.strip()]:
            parsed = self._parse(raw)
            if parsed:
                out.append(parsed)
        return out

    @staticmethod
    def _parse(raw):
        lines = raw.strip().splitlines()
        if not lines:
            return None
        tag = lines[0].strip()
        if not (tag.startswith('[') and tag.endswith(']')):
            return None
        f = [x.strip() for x in tag[1:-1].split('|')]
        if len(f) < 4:
            return None
        resolved = None
        for x in f[3:]:
            if x.startswith('resolved:'):
                resolved = x[len('resolved:'):].strip()
        body = "\n".join(lines[1:]).strip()
        dm = _DECISION_RE.search(body)
        rm = _REFLECTION_RE.search(body)
        return {
            'date': f[0], 'name': f[1], 'rating': f[2],
            'pending': f[3] == 'pending',
            'raw': None if f[3] == 'pending' else f[3],
            'alpha': f[4] if len(f) > 4 and not f[4].startswith('resolved:') else None,
            'holding': f[5] if len(f) > 5 and not f[5].startswith('resolved:') else None,
            'resolved': resolved,
            'decision': dm.group(1).strip() if dm else '',
            'reflection': rm.group(1).strip() if rm else '',
        }

    def get_pending(self):
        return [e for e in self.load_entries() if e['pending']]

    def get_past_context(self, name, n_same=5, n_cross=3, as_of=None):
        """프롬프트 주입용 과거 맥락. pending 은 결과를 모르므로 제외한다."""
        entries = [e for e in self.load_entries() if not e['pending']]
        if as_of is not None:
            entries = [e for e in entries if e.get('resolved') and e['resolved'] <= as_of]
        if not entries:
            return ''
        same, cross = [], []
        for e in reversed(entries):
            if len(same) >= n_same and len(cross) >= n_cross:
                break
            if e['name'] == name and len(same) < n_same:
                same.append(e)
            elif e['name'] != name and len(cross) < n_cross:
                cross.append(e)
        parts = []
        if same:
            parts.append(f"## {name} 과거 분석 (최신순)\n")
            for e in same:
                parts.append(
                    f"[{e['date']} | {e['rating']} | raw {e['raw']} | alpha {e['alpha']} | "
                    f"{e['holding']}]\nDECISION:\n{e['decision']}\n"
                    + (f"REFLECTION:\n{e['reflection']}\n" if e['reflection'] else ''))
        if cross:
            parts.append("## 타 종목 최근 교훈\n")
            for e in cross:
                txt = e['reflection'] or e['decision'][:250]
                parts.append(f"[{e['date']} | {e['name']} | {e['rating']} | alpha {e['alpha']}]\n{txt}\n")
        return "\n".join(parts)

    def stats(self):
        entries = self.load_entries()
        res = [e for e in entries if not e['pending'] and e['alpha']]
        alphas, verdicts = [], []
        for e in res:
            try:
                a = float(e['alpha'].replace('%', '').replace('+', ''))
            except (ValueError, AttributeError):
                continue
            alphas.append(a)
            verdicts.append(score(e['rating'], a))
        judged = [v for v in verdicts if v != 'N/A']
        hits = sum(1 for v in judged if v == 'HIT')
        return {
            'total': len(entries),
            'resolved': len(res),
            'pending': len(entries) - len(res),
            'hit': hits,
            'judged': len(judged),
            'avg_alpha': (sum(alphas) / len(alphas)) if alphas else 0.0,
            'hit_rate': (hits / len(judged) * 100) if judged else 0.0,
        }


# ==================== 수익률 계산 ====================

def fetch_returns(name, market, start_date, end_date=None):
    """(raw, alpha, holding_days, resolution_date) 반환. 실패 시 None."""
    end_date = end_date or date.today().isoformat()
    try:
        if market == 'US':
            import yfinance as yf
            px = yf.Ticker(name).history(start=start_date, end=end_date)['Close']
            bm = yf.Ticker('SPY').history(start=start_date, end=end_date)['Close']
            bm_label = 'SPY'
        else:
            import FinanceDataReader as fdr
            code, mkt = _resolve_kr_meta(name)
            if not code:
                print(f"  [WARN] {name} 종목코드 확인 실패")
                return None
            px = fdr.DataReader(code, start_date, end_date)['Close']
            # 지수 심볼(KS11/KQ11)은 FDR 0.9.101 에서 ValueError: LOGOUT 으로 죽는다.
            # ETF 를 대용지수로 쓴다 (volatility_beta.py 와 동일한 기준).
            if (mkt or '').upper().startswith('KOSDAQ'):
                bm_code, bm_label = '229200', 'KODEX 코스닥150'
            else:
                bm_code, bm_label = '069500', 'KODEX 200'
            bm = fdr.DataReader(bm_code, start_date, end_date)['Close']
        if len(px) < 2 or len(bm) < 2:
            return None
        raw = float(px.iloc[-1]) / float(px.iloc[0]) - 1
        bmr = float(bm.iloc[-1]) / float(bm.iloc[0]) - 1
        days = (px.index[-1] - px.index[0]).days
        res_date = str(px.index[-1].date())
        return raw, raw - bmr, days, res_date, bm_label
    except Exception as e:
        print(f"  [WARN] {name} 수익률 조회 실패: {type(e).__name__}: {e}")
        return None


def _resolve_kr_meta(name):
    """analysis.json 에서 (종목코드, 시장) 반환. 시장은 벤치마크 선택에 쓴다."""
    p = f'scripts/analysis_{name}.json'
    if os.path.exists(p):
        try:
            meta = (json.load(open(p, encoding='utf-8')).get('meta') or {})
            code = meta.get('stock_code')
            if code:
                return str(code).zfill(6), meta.get('market', '')
        except Exception:
            pass
    return None, ''


# ==================== CLI ====================

def cmd_record(args):
    name = args[0]
    p = f'scripts/analysis_{name}.json'
    if not os.path.exists(p):
        print(f"[ERR] {p} 없음")
        return 1
    d = json.load(open(p, encoding='utf-8'))
    meta, op, price = d.get('meta', {}), d.get('opinion', {}), d.get('price', {})
    market = 'US' if (meta.get('country') or '').upper() in ('US', 'USA') else 'KR'
    trade_date = meta.get('date') or date.today().isoformat()
    trade_date = re.sub(r'[^\d\-]', '', str(trade_date))[:10] or date.today().isoformat()
    log = DecisionLog()
    ok = log.store_decision(
        name=name, trade_date=trade_date, rating=op.get('rating', 'N/A'),
        thesis=(d.get('sections', {}).get('s01_opinion_thesis', '') or '')[:400],
        targets={'bear': op.get('target_bear'), 'base': op.get('target_base'),
                 'bull': op.get('target_bull')},
        price=price.get('current'), market=market)
    print(f"[{'OK' if ok else 'SKIP'}] {name} {trade_date} {op.get('rating')} "
          f"{'기록' if ok else '이미 존재 (멱등)'}")
    return 0


def cmd_settle(args):
    log = DecisionLog()
    targets = log.get_pending()
    note = ''
    if '--note' in args:
        note = args[args.index('--note') + 1]
        args = args[:args.index('--note')]
    if args:
        targets = [e for e in targets if e['name'] == args[0]]
    if not targets:
        print("정산할 pending 항목이 없습니다.")
        return 0
    for e in targets:
        market = 'US' if re.fullmatch(r'[A-Z.]{1,6}', e['name']) else 'KR'
        r = fetch_returns(e['name'], market, e['date'])
        if not r:
            print(f"  [SKIP] {e['name']} {e['date']} -- 수익률 계산 불가")
            continue
        raw, alpha, days, res_date, bm = r
        log.update_with_outcome(e['name'], e['date'], raw, alpha, days,
                                reflection=note, resolution_date=res_date)
        mark = score(e['rating'], alpha * 100).ljust(4)
        print(f"  [{mark}] {e['name']:<12} {e['date']} {e['rating']:<6} "
              f"raw {raw:+.1%} / alpha vs {bm} {alpha:+.1%} / {days}d")
    return 0


def cmd_pending(args):
    for e in DecisionLog().get_pending():
        print(f"  {e['date']}  {e['name']:<14} {e['rating']:<6} (미정산)")
    return 0


def cmd_context(args):
    if not args:
        print("usage: decision_log.py context {종목명} [--as-of YYYY-MM-DD]")
        return 1
    as_of = args[args.index('--as-of') + 1] if '--as-of' in args else None
    ctx = DecisionLog().get_past_context(args[0], as_of=as_of)
    print(ctx or "(과거 정산 기록 없음)")
    return 0


def cmd_stats(args):
    s = DecisionLog().stats()
    print(f"\n  총 {s['total']}건 / 정산 {s['resolved']}건 / 대기 {s['pending']}건")
    if s['resolved']:
        print(f"  방향 적중 {s['hit']}/{s['judged']} ({s['hit_rate']:.0f}%) / "
              f"평균 alpha {s['avg_alpha']:+.2f}%")
        print(f"  (BUY: alpha>0 / SELL: alpha<0 / HOLD: |alpha|<={HOLD_BAND:.0f}% 이면 적중)")
    else:
        print("  정산된 기록이 없습니다. `settle` 을 먼저 실행하세요.")
    return 0


COMMANDS = {'record': cmd_record, 'settle': cmd_settle, 'pending': cmd_pending,
            'context': cmd_context, 'stats': cmd_stats}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: python scripts/decision_log.py {{{'|'.join(COMMANDS)}}} [args]")
        sys.exit(1)
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))
