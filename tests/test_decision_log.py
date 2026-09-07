"""
decision_log 테스트 (TDD -- 구현보다 먼저 작성됨)

결정 로그는 '46개 리포트를 냈는데 적중률을 아무도 모른다' 는 구멍을 메운다.
파일이 깨지면 과거 기록 전체가 날아가므로, 원자적 쓰기와 파싱 왕복(round-trip)을
테스트로 고정한다.

실행: python tests/test_decision_log.py
"""
import sys
import os
import io
import tempfile
import shutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

from decision_log import DecisionLog, score, HOLD_BAND, resolve_market, flag_value

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected!r}\n      실제: {actual!r}")


def truthy(actual, name):
    eq(bool(actual), True, name)


tmpdir = tempfile.mkdtemp(prefix='dlog_test_')
log_path = os.path.join(tmpdir, '_decision_log.md')

try:
    log = DecisionLog(log_path)

    # --- 1. 기록 + 왕복 파싱 ---
    log.store_decision('와이지엔터', '2026-05-15', 'BUY',
                       thesis='신인 데뷔 사이클 진입',
                       targets={'bear': 40000, 'base': 62000, 'bull': 80000},
                       price=48000, market='KR')
    entries = log.load_entries()
    eq(len(entries), 1, "1건 기록 후 1건 파싱")
    e = entries[0]
    eq(e['name'], '와이지엔터', "종목명 왕복")
    eq(e['rating'], 'BUY', "등급 왕복")
    eq(e['pending'], True, "최초 기록은 pending")
    truthy('신인 데뷔' in e['decision'], "thesis 본문 보존")

    # --- 2. 멱등성: 같은 (날짜, 종목) 재기록은 중복을 만들지 않는다 ---
    log.store_decision('와이지엔터', '2026-05-15', 'BUY', thesis='중복 시도', price=48000)
    eq(len(log.load_entries()), 1, "같은 날짜+종목 재기록은 무시 (멱등)")

    # --- 3. 여러 종목 ---
    log.store_decision('한국콜마', '2026-06-01', 'HOLD', thesis='화장품 ODM 사이클',
                       price=161700, market='KR')
    log.store_decision('AMD', '2026-06-10', 'BUY', thesis='MI400 램프',
                       price=347.81, market='US')
    eq(len(log.load_entries()), 3, "3건 누적")
    eq(len(log.get_pending()), 3, "전부 pending")

    # --- 4. 정산: alpha 기록 + REFLECTION 추가 ---
    log.update_with_outcome('와이지엔터', '2026-05-15',
                            raw_return=0.182, alpha_return=0.114,
                            holding_days=90, resolution_date='2026-08-13',
                            reflection='방향성 적중. 신인 데뷔가 아니라 일본 공연 매출이 견인했다.')
    e = [x for x in log.load_entries() if x['name'] == '와이지엔터'][0]
    eq(e['pending'], False, "정산 후 pending 해제")
    eq(e['raw'], '+18.2%', "raw 수익률 기록")
    eq(e['alpha'], '+11.4%', "alpha 기록")
    eq(e['holding'], '90d', "보유일수 기록")
    eq(e['resolved'], '2026-08-13', "결과 확정일 기록")
    truthy('일본 공연' in e['reflection'], "reflection 본문 보존")
    eq(len(log.get_pending()), 2, "정산 후 pending 2건")

    # --- 5. 정산해도 다른 항목이 손상되지 않는다 ---
    others = [x['name'] for x in log.load_entries()]
    eq(sorted(others), sorted(['와이지엔터', '한국콜마', 'AMD']), "정산 후에도 3건 전부 보존")

    # --- 6. 과거 맥락 주입 문자열 ---
    log.store_decision('와이지엔터', '2026-09-01', 'HOLD', thesis='2차 점검', price=56000)
    log.update_with_outcome('와이지엔터', '2026-09-01', raw_return=-0.05, alpha_return=-0.09,
                            holding_days=30, resolution_date='2026-10-01',
                            reflection='밸류 부담 과소평가.')
    ctx = log.get_past_context('와이지엔터', n_same=5, n_cross=3)
    truthy('와이지엔터' in ctx, "맥락에 같은 종목 포함")
    truthy('일본 공연' in ctx, "맥락에 과거 reflection 포함")

    # --- 7. point-in-time 필터: 아직 안 알려진 결과는 주입하지 않는다 ---
    ctx_early = log.get_past_context('와이지엔터', as_of='2026-08-20')
    truthy('일본 공연' in ctx_early, "8/13 확정 결과는 8/20 시점에 알려져 있다")
    eq('밸류 부담' in ctx_early, False,
       "10/01 확정 결과는 8/20 시점에 미래 정보이므로 제외 (look-ahead 차단)")

    # --- 8. pending 은 맥락에 넣지 않는다 (결과를 모르므로 교훈이 없다) ---
    ctx_all = log.get_past_context('한국콜마')
    eq('화장품 ODM 사이클' in ctx_all, False, "pending 항목은 맥락에서 제외")

    # --- 9. 통계 ---
    stats = log.stats()
    eq(stats['total'], 4, "총 4건")
    eq(stats['resolved'], 2, "정산 2건")
    eq(stats['pending'], 2, "pending 2건")
    # 방향 인식 채점: BUY +11.4% -> HIT, HOLD -9.0% (|alpha| <= 10) -> HIT
    eq(stats['hit'], 2, "방향 적중 2건 (BUY 상승 / HOLD 소폭)")
    eq(stats['judged'], 2, "채점 대상 2건")
    truthy(abs(stats['avg_alpha'] - 1.2) < 0.01,
           f"평균 alpha (+11.4 + -9.0)/2 = +1.2 (실제 {stats.get('avg_alpha')})")
    truthy(abs(stats['hit_rate'] - 100.0) < 0.01, "적중률 2/2 = 100%")

    # --- 9b. 방향 인식 채점 ---
    eq(score('BUY', 11.6), 'HIT', "BUY + alpha 양수 -> HIT")
    eq(score('BUY', -15.4), 'MISS', "BUY + alpha 음수 -> MISS")
    eq(score('SELL', -8.0), 'HIT', "SELL + alpha 음수 -> HIT")
    eq(score('SELL', 8.0), 'MISS', "SELL + alpha 양수 -> MISS")
    eq(score('HOLD', -9.4), 'HIT', "HOLD + 소폭 변동 -> HIT (크게 안 움직인다는 주장이 맞음)")
    eq(score('HOLD', -12.8), 'MISS', "HOLD + 큰 하락 -> MISS (SELL 을 냈어야 했다)")
    eq(score('HOLD', 10.9), 'MISS', "HOLD + 큰 상승 -> MISS (BUY 를 냈어야 했다)")
    eq(score('Overweight', 3.0), 'HIT', "Overweight 5단계 등급 인식")
    eq(score('Underweight', -3.0), 'HIT', "Underweight 5단계 등급 인식")
    eq(score('매수', 5.0), 'HIT', "한글 등급 '매수' 인식")
    eq(score('N/A', 5.0), 'N/A', "미상 등급 -> 채점 제외")
    eq(score('BUY', None), 'N/A', "alpha 없으면 채점 제외")
    truthy(HOLD_BAND > 0, "HOLD 밴드 상수 존재")

    # --- 9c. market 지속 (v5.5 리뷰: JYP/LS 를 미국 종목으로 오판) ---
    # 초판은 정산 시점에 종목명 정규식 [A-Z.]{1,6} 으로 시장을 다시 추측했다.
    # JYP(035900, KOSDAQ) / LS(006260, KOSPI) 가 US 로 분류돼
    # yf.Ticker('LS') = Lands' End 의 주가로 alpha 를 계산하고도 에러 없이 기록됐다.
    log.store_decision('LS', '2026-07-01', 'BUY', thesis='지주 재평가',
                       price=180000, market='KR')
    ls = [x for x in log.load_entries() if x['name'] == 'LS'][0]
    eq(ls.get('market'), 'KR', "store_decision 이 market 을 로그에 남긴다")

    log.update_with_outcome('LS', '2026-07-01', 0.10, 0.05, 60,
                            resolution_date='2026-08-30', reflection='r')
    ls2 = [x for x in log.load_entries() if x['name'] == 'LS'][0]
    eq(ls2.get('market'), 'KR', "정산 후에도 market 이 보존된다")
    eq(ls2['alpha'], '+5.0%', "정산 값이 정상 기록")

    # 기록에 market 이 있으면 그것을 쓴다 (이름 정규식보다 우선)
    eq(resolve_market({'name': 'LS', 'market': 'KR'}), 'KR', "기록된 market 우선")
    eq(resolve_market({'name': 'AMD', 'market': 'US'}), 'US', "US 기록도 그대로")

    # 구버전 항목(market 없음)은 analysis.json 의 meta 로 되찾는다
    eq(resolve_market({'name': 'JYP'}), 'KR',
       "market 미기록 JYP -> analysis.json meta.country=KR 로 복구")
    eq(resolve_market({'name': 'LS'}), 'KR',
       "market 미기록 LS -> analysis.json meta.country=KR 로 복구")
    eq(resolve_market({'name': 'AMD'}), 'US', "market 미기록 AMD -> US")
    eq(resolve_market({'name': '없는종목XYZ'}), 'KR',
       "정보가 전혀 없으면 KR 로 보수 처리 (틀린 미국 티커 조회보다 안전)")

    # --- 9d. CLI 플래그 파싱 (리뷰: flag 가 마지막 인자면 IndexError) ---
    eq(flag_value(['settle', '--note', 'abc'], '--note'), 'abc', "정상 값 추출")
    eq(flag_value(['settle', '--note'], '--note', ''), '', "flag 가 마지막 -> default (IndexError 아님)")
    eq(flag_value(['settle', '--note', '--as-of'], '--note', ''), '',
       "다음 토큰이 또 다른 flag -> default")
    eq(flag_value(['settle'], '--note', 'x'), 'x', "flag 없음 -> default")

    # --- 10. 파일이 깨지지 않는다 (원자적 쓰기 왕복) ---
    raw_text = open(log_path, encoding='utf-8').read()
    truthy(raw_text.count('<!-- ENTRY_END -->') >= 5, "구분자가 항목 수만큼 존재")
    log2 = DecisionLog(log_path)
    eq(len(log2.load_entries()), 5, "새 인스턴스에서 재파싱 성공 (LS 포함 5건)")

    # --- 11. 존재하지 않는 항목 정산은 조용히 무시 ---
    log.update_with_outcome('없는종목', '2020-01-01', 0.1, 0.1, 10, reflection='x')
    eq(len(log.load_entries()), 5, "없는 항목 정산은 파일을 훼손하지 않는다")

finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

print(f"\n{'=' * 60}")
print(f"  decision_log 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
