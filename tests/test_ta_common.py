"""ta_common.py 테스트 -- /research-ta 공용 헬퍼 (Task 1).

네트워크 금지. resolve_stock 의 FDR 폴백은 listing 인자로 DataFrame 을
주입해 대체한다 (미매칭 케이스는 빈 DataFrame 을 넣어 실제 fdr.StockListing
호출을 막는다).

실행: python tests/test_ta_common.py
"""
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import pandas as pd                                     # noqa: E402
import ta_common as tc                                  # noqa: E402

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

_passed = 0
_failed = []


def eq(got, want, label):
    global _passed
    if got == want:
        _passed += 1
    else:
        _failed.append((label, want, got))


def raises(exc_type, fn, label):
    global _passed
    try:
        fn()
    except exc_type:
        _passed += 1
        return
    except Exception as e:
        _failed.append((label, f'{exc_type.__name__}', f'{type(e).__name__}: {e}'))
        return
    _failed.append((label, f'{exc_type.__name__}', '예외 없음'))


# ==================== ta_dir / data_dir ====================
raises(ValueError, lambda: tc.ta_dir('../etc'), 'ta_dir 는 .. 을 거부한다')
raises(ValueError, lambda: tc.ta_dir('a/b'), 'ta_dir 는 / 를 거부한다')
raises(ValueError, lambda: tc.ta_dir('a\\b'), 'ta_dir 는 \\ 를 거부한다')

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        d = tc.ta_dir('테스트종목')
        eq(os.path.isdir(d), True, 'ta_dir 는 폴더를 실제로 만든다')
        eq(d, os.path.join(td, 'data', '테스트종목', 'ta'), 'ta_dir 경로 조합')
        eq(tc.data_dir('테스트종목'), os.path.join(td, 'data', '테스트종목'),
           'data_dir 는 만들지 않고 경로만')
        eq(os.path.isdir(tc.data_dir('다른종목')), False, 'data_dir 는 폴더를 만들지 않는다')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== write_json / read_json ====================
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, 'x.json')
    tc.write_json(p, {'a': 1, 'b': '값'})
    eq(tc.read_json(p), {'a': 1, 'b': '값'}, 'write_json -> read_json 왕복 일치')
    eq(tc.read_json(os.path.join(td, '없음.json'), default={'z': 0}), {'z': 0},
       '파일 없으면 default')
    eq(tc.read_json(os.path.join(td, '없음2.json')), None, 'default 생략 시 None')

    broken = os.path.join(td, 'broken.json')
    with open(broken, 'w', encoding='utf-8') as f:
        f.write('{이거 json 아님')
    raises(json.JSONDecodeError, lambda: tc.read_json(broken), '깨진 JSON 은 예외를 그대로 올린다')

    # 원자적 쓰기: 임시파일이 남지 않는다
    tc.write_json(p, {'c': 2})
    leftovers = [f for f in os.listdir(td) if f.startswith('.tmp')]
    eq(leftovers, [], '쓰기 후 임시파일이 남지 않는다')

# ==================== resolve_stock ====================
# 실측 KRX-DESC 컬럼 (fdr.StockListing('KRX') 은 프로덕션에서 죽어 있다 -- KRX-DESC 만 쓴다)
KRX_DESC_COLUMNS = ['Code', 'Name', 'Market', 'Sector', 'Industry', 'ListingDate',
                    'SettleMonth', 'Representative', 'HomePage', 'Region']
LISTING = pd.DataFrame([
    {'Code': '036810', 'Name': '에프에스티', 'Market': 'KOSDAQ', 'Sector': '', 'Industry': '',
     'ListingDate': '', 'SettleMonth': '12월', 'Representative': '', 'HomePage': '', 'Region': ''},
    {'Code': '051500', 'Name': 'CJ프레시웨이', 'Market': 'KOSDAQ', 'Sector': '', 'Industry': '',
     'ListingDate': '', 'SettleMonth': '12월', 'Representative': '', 'HomePage': '', 'Region': ''},
    {'Code': '031980', 'Name': '피에스케이홀딩스', 'Market': 'KOSDAQ GLOBAL', 'Sector': '',
     'Industry': '', 'ListingDate': '', 'SettleMonth': '12월', 'Representative': '',
     'HomePage': '', 'Region': ''},
    {'Code': '005930', 'Name': '삼성전자', 'Market': 'KOSPI', 'Sector': '', 'Industry': '',
     'ListingDate': '', 'SettleMonth': '12월', 'Representative': '', 'HomePage': '', 'Region': ''},
    {'Code': '999999', 'Name': '코넥스종목', 'Market': 'KONEX', 'Sector': '', 'Industry': '',
     'ListingDate': '', 'SettleMonth': '12월', 'Representative': '', 'HomePage': '', 'Region': ''},
], columns=KRX_DESC_COLUMNS)

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        # (a) code 인자 + KRX-DESC listing 주입 -> KOSDAQ 229200 / .KQ / settle_month
        r = tc.resolve_stock('에프에스티', code='036810', listing=LISTING)
        eq(r['code'], '036810', 'code 인자를 그대로 쓴다')
        eq(r['market'], 'KOSDAQ', 'market 은 listing 으로 채운다')
        eq(r['benchmark_code'], '229200', 'KOSDAQ -> 229200')
        eq(r['benchmark_name'], 'KODEX 코스닥150', 'KOSDAQ 벤치마크명')
        eq(r['yahoo'], '036810.KQ', 'KOSDAQ -> .KQ')
        eq(r['settle_month'], '12월', 'settle_month 은 KRX-DESC SettleMonth 에서 온다')

        # KOSDAQ GLOBAL 도 KOSDAQ 취급 (startswith 'KOSDAQ')
        r_global = tc.resolve_stock('피에스케이홀딩스', code='031980', listing=LISTING)
        eq(r_global['market'], 'KOSDAQ GLOBAL', 'market 값 자체는 원본 그대로 보존')
        eq(r_global['benchmark_code'], '229200', 'KOSDAQ GLOBAL -> 229200')
        eq(r_global['yahoo'], '031980.KQ', 'KOSDAQ GLOBAL -> .KQ')

        r2 = tc.resolve_stock('삼성전자', code='005930', listing=LISTING)
        eq(r2['benchmark_code'], '069500', 'KOSPI -> 069500')
        eq(r2['yahoo'], '005930.KS', 'KOSPI -> .KS')

        # KONEX -> 벤치마크는 KOSPI ETF, yahoo 는 None + note
        r_konex = tc.resolve_stock('코넥스종목', code='999999', listing=LISTING)
        eq(r_konex['benchmark_code'], '069500', 'KONEX -> 벤치마크 069500')
        eq(r_konex['yahoo'], None, 'KONEX -> yahoo 티커 없음(None)')
        eq(r_konex['note'] is not None and 'KONEX' in r_konex['note'], True,
           'KONEX 는 note 로 사유를 남긴다')
        eq(r['note'], None, 'KOSDAQ 는 note 없음')

        # (b) analysis.json meta 경로
        os.makedirs(os.path.join(td, 'scripts'), exist_ok=True)
        with open(os.path.join(td, 'scripts', 'analysis_가짜종목.json'), 'w', encoding='utf-8') as f:
            json.dump({'meta': {'stock_code': '123456', 'market': 'KOSPI'}}, f)
        r3 = tc.resolve_stock('가짜종목')
        eq(r3['code'], '123456', 'analysis.json meta.stock_code 로 찾는다')
        eq(r3['market'], 'KOSPI', 'analysis.json meta.market 도 그대로 쓴다')
        eq(r3['source'], 'analysis_json', 'source 필드가 출처를 밝힌다')
        eq(r3['settle_month'], None,
           'listing 을 안 거쳤으면 settle_month 는 None (여기서 새 fetch 를 만들지 않는다)')

        # (c) 아무 데도 없으면 LookupError (빈 listing + KRX 도 빈 응답으로 네트워크 폴백 차단)
        _no_krx = lambda path, basDd: []  # noqa: E731
        raises(LookupError,
               lambda: tc.resolve_stock('없는종목', listing=pd.DataFrame(columns=KRX_DESC_COLUMNS),
                                         krx_call=_no_krx),
               '어디서도 못 찾으면 LookupError')

        # market 을 끝내 확정 못 하면 (코드는 있는데 market 빈 값 + detect_market 도 실패 +
        # KRX Open API 도 빈 응답) 조용히 기본 벤치마크로 넘어가지 않고 LookupError 를 낸다.
        import volatility_beta as _vb
        _orig_detect = _vb.detect_market
        _vb.detect_market = lambda code: None
        try:
            no_market_row = pd.DataFrame([
                {'Code': '777777', 'Name': '시장모름', 'Market': '', 'Sector': '', 'Industry': '',
                 'ListingDate': '', 'SettleMonth': '', 'Representative': '', 'HomePage': '',
                 'Region': ''},
            ], columns=KRX_DESC_COLUMNS)
            raises(LookupError,
                   lambda: tc.resolve_stock('시장모름', code='777777', listing=no_market_row,
                                             krx_call=_no_krx),
                   'market 을 확정 못 하면 조용히 기본값을 쓰지 않고 LookupError')
        finally:
            _vb.detect_market = _orig_detect

        # ---------- KRX Open API 폴백 (Task 14) ----------
        # (d) 이름으로도 못 찾았을 때: KRX 기본정보(코스닥 종목기본정보)에 약칭/정식명이
        # 있으면 code+market 을 함께 채우고 source 는 'krx_open'.
        def _krx_name_hit(path, basDd):
            if path == 'sto/ksq_isu_base_info':
                return [{'ISU_SRT_CD': '036810', 'ISU_NM': '에프에스티', 'ISU_ABBRV': '에프에스티'}]
            return []

        r_krx_name = tc.resolve_stock('에프에스티', listing=pd.DataFrame(columns=KRX_DESC_COLUMNS),
                                       krx_call=_krx_name_hit)
        eq(r_krx_name['code'], '036810', 'KRX 기본정보 이름 일치로 code 를 찾는다')
        eq(r_krx_name['market'], 'KOSDAQ', 'ksq_isu_base_info 매칭 -> KOSDAQ')
        eq(r_krx_name['source'], 'krx_open', 'KRX Open API 로 채웠으면 source 는 krx_open')

        # (e) code 는 이미 아는데(=code_arg) listing/detect_market 이 전부 market 을 못 정했을 때:
        # KRX 기본정보에서 그 code 가 있는 엔드포인트(KOSPI)로 market 만 채운다.
        _vb.detect_market = lambda code: None
        try:
            def _krx_code_hit(path, basDd):
                if path == 'sto/stk_isu_base_info':
                    return [{'ISU_SRT_CD': '005930', 'ISU_NM': '삼성전자', 'ISU_ABBRV': '삼성전자'}]
                return []

            r_krx_code = tc.resolve_stock('삼성전자', code='005930', krx_call=_krx_code_hit)
            eq(r_krx_code['market'], 'KOSPI', 'code 는 이미 알고 KRX 기본정보로 market 만 채운다')
            eq(r_krx_code['source'], 'krx_open', 'market 을 KRX Open API 로 채웠으면 source 도 krx_open')
        finally:
            _vb.detect_market = _orig_detect

        # (f) KRX 호출 자체가 실패(예외) + 나머지도 실패 -> 여전히 LookupError,
        # attempts 에 KRX 실패 사유가 섞여 들어간다.
        def _krx_raises(path, basDd):
            raise TimeoutError('KRX 서버 응답 없음')

        try:
            tc.resolve_stock('없는종목2', listing=pd.DataFrame(columns=KRX_DESC_COLUMNS),
                              krx_call=_krx_raises)
            _failed.append(('KRX 실패 + 나머지 실패 -> LookupError', 'LookupError', '예외 없음'))
        except LookupError as e:
            _passed_local = 'KRX' in str(e) and 'TimeoutError' in str(e)
            eq(_passed_local, True, 'KRX 호출 실패 사유가 LookupError 메시지(attempts)에 남는다')
        except Exception as e:
            _failed.append(('KRX 실패 + 나머지 실패 -> LookupError', 'LookupError', f'{type(e).__name__}: {e}'))
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== krx_call_with_fallback -- 주말/17시 이전 폴백 ====================
from datetime import datetime as _dt  # noqa: E402

# (a) 평일 17시 이전 -> basDd 는 '오늘'이 아니라 '전 거래일'부터 시작한다.
_calls = []


def _krx_record(path, basDd):
    _calls.append(basDd)
    return [{'ok': True}] if basDd == '20250910' else []


_rows_a, _basdd_a, _reasons_a = tc.krx_call_with_fallback(
    'sto/stk_bydd_trd', krx_call=_krx_record,
    now=_dt(2025, 9, 11, 9, 0, tzinfo=tc.KST))  # 2025-09-11 목요일 09:00 (17시 이전)
eq(_basdd_a, '20250910', '평일 17시 이전이면 전 거래일부터 조회')
eq(_rows_a, [{'ok': True}], '데이터가 있는 basDd 에서 즉시 반환')

# (b) 토요일 + 빈 응답 -> 금요일 -> ... 평일만 건너뛰며 최대 5회, 주말은 건너뛰되 호출하지 않는다.
_calls.clear()


def _krx_empty(path, basDd):
    _calls.append(basDd)
    return []


_rows_b, _basdd_b, _reasons_b = tc.krx_call_with_fallback(
    'sto/stk_bydd_trd', krx_call=_krx_empty,
    now=_dt(2025, 9, 13, 20, 0, tzinfo=tc.KST))  # 2025-09-13 토요일 20:00
eq(_rows_b, [], '전부 빈 응답이면 rows=[]')
eq(all(_dt.strptime(b, '%Y%m%d').weekday() < 5 for b in _calls), True,
   '토요일에 호출해도 실제 조회 basDd 는 전부 평일이다(주말 skip)')
eq(len(_calls), 5, '최대 max_lookback(5) 회만 시도한다')
eq(any('빈 응답' in r for r in _reasons_b), True, '실패 사유가 reasons 에 남는다')

# (c) 호출 자체가 예외를 던지면 reasons 에 예외타입/메시지가 남고 다음 날짜로 계속 진행한다.
_rows_c, _basdd_c, _reasons_c = tc.krx_call_with_fallback(
    'sto/stk_bydd_trd', krx_call=lambda path, basDd: (_ for _ in ()).throw(RuntimeError('boom')),
    now=_dt(2025, 9, 11, 9, 0, tzinfo=tc.KST), max_lookback=2)
eq(_rows_c, [], '전부 예외면 rows=[]')
eq(len(_reasons_c) >= 2, True, '예외 사유가 매 시도마다 기록된다(+ 최종 요약 1개)')
eq(all('RuntimeError' in r or '빈 응답' in r for r in _reasons_c), True,
   '예외 사유 문자열에 예외 타입이 포함된다')

# ==================== name_variants ====================
eq(tc.name_variants('LS일렉트릭')[:2], ['LS일렉트릭', '엘에스일렉트릭'],
   'corp_name_resolver.variants 를 그대로 넘긴다')

# ==================== is_reaction_title ====================
eq(tc.is_reaction_title('[특징주] 에프에스티, 삼성 납품 소식에 급등'), True,
   '특징주+급등 기사는 반응 기사')
eq(tc.is_reaction_title('에프에스티, EUV 펠리클 양산 공급 계약'), False,
   '공급계약 기사는 반응 기사가 아니다')

# Task 14 실측 누락: '주가 ' substring(공백 필수)이 '주가,' 를 못 잡던 것을 정규식으로 보강
eq(tc.is_reaction_title('에프에스티 주가, 4월 30일 42,500원 1.62% 하락 마감'), True,
   '주가+쉼표 / N.N%+하락 / 하락 마감 전부 정규식으로 잡는다')
eq(tc.is_reaction_title('에프에스티, CNT 펠리클 생산능력 확대…카나투 장비 추가 도입'), False,
   '생산능력 확대 기사는 반응 기사가 아니다')

# Task 14 part 3 추가 실측(컨트롤러 지적): 화살표 등락 표기도 반응 기사다
eq(tc.is_reaction_title('에프에스티 10%↑ 마이크로컨텍솔 9%↑… 반도체 재료 부품주에 무슨'), True,
   'N%+화살표(↑↓▲▼) 도 정규식으로 잡는다')

# ==================== manifest_update ====================
with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        raises(ValueError, lambda: tc.manifest_update('종목', 'step1', 'bogus'),
               '허용되지 않은 status 는 ValueError')

        m1 = tc.manifest_update('종목', 'collect', 'ok', count=5)
        eq(m1['steps']['collect']['status'], 'ok', 'status 저장')
        eq(m1['steps']['collect']['count'], 5, '추가 detail 저장')
        eq('at' in m1['steps']['collect'], True, 'at 타임스탬프 포함')

        m2 = tc.manifest_update('종목', 'verify', 'failed', reason='timeout')
        eq(set(m2['steps'].keys()), {'collect', 'verify'}, '두 step 이 누적된다')
        eq(m2['steps']['collect']['status'], 'ok', '이전 step 은 그대로 남는다')
        eq(m2['steps']['verify']['status'], 'failed', '새 step 상태 반영')

        manifest_path = os.path.join(tc.ta_dir('종목'), 'manifest.json')
        on_disk = json.load(open(manifest_path, encoding='utf-8'))
        eq(on_disk['steps']['verify']['reason'], 'timeout', '파일에도 원자적으로 반영된다')
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== now_kst / KST ====================
now = tc.now_kst()
eq(now.utcoffset().total_seconds(), 9 * 3600, 'now_kst 는 UTC+9')
eq(now.tzinfo is tc.KST or now.utcoffset() == tc.KST.utcoffset(None), True,
   'now_kst 는 KST 타임존을 쓴다')

print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_common 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
