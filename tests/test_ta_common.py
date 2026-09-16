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

        # (c) 아무 데도 없으면 LookupError (빈 listing 으로 네트워크 폴백 차단)
        raises(LookupError, lambda: tc.resolve_stock('없는종목', listing=pd.DataFrame(columns=KRX_DESC_COLUMNS)),
               '어디서도 못 찾으면 LookupError')

        # market 을 끝내 확정 못 하면 (코드는 있는데 market 빈 값 + detect_market 도 실패)
        # 조용히 기본 벤치마크로 넘어가지 않고 LookupError 를 낸다.
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
                   lambda: tc.resolve_stock('시장모름', code='777777', listing=no_market_row),
                   'market 을 확정 못 하면 조용히 기본값을 쓰지 않고 LookupError')
        finally:
            _vb.detect_market = _orig_detect
    finally:
        tc.PROJECT_ROOT = orig_root

# ==================== name_variants ====================
eq(tc.name_variants('LS일렉트릭')[:2], ['LS일렉트릭', '엘에스일렉트릭'],
   'corp_name_resolver.variants 를 그대로 넘긴다')

# ==================== is_reaction_title ====================
eq(tc.is_reaction_title('[특징주] 에프에스티, 삼성 납품 소식에 급등'), True,
   '특징주+급등 기사는 반응 기사')
eq(tc.is_reaction_title('에프에스티, EUV 펠리클 양산 공급 계약'), False,
   '공급계약 기사는 반응 기사가 아니다')

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
