"""macro_data 모듈 테스트 (2026-09 신설)

실행: python tests/test_macro_data.py
     python tests/test_macro_data.py --net      (FRED/ECOS 실호출 테스트 추가)

배경: 리포트의 거시 서술이 전부 WebSearch 요약이라 시점/출처가 흔들렸다.
      FRED(미 연준) + ECOS(한국은행) 실측 시계열로 대체한다.

이 테스트가 지키려는 것은 "파싱이 되는가" 보다 **"실패를 실패라고 말하는가"** 다.
FnGuide 가 URL 이전으로 죽었는데 except 로 삼켜 몇 달간 아무도 몰랐던 사고를 반복하지 않는다.
특히 ECOS 는 **인증 오류/데이터 없음에도 HTTP 200** 을 주고 본문에 RESULT 블록만 넣는다.
상태코드만 보면 조용히 성공으로 오인하는 구조라 반드시 본문을 검사해야 한다.

픽스처: tests/fixtures/fred_*.json, ecos_*.json (실제 응답 1회 저장본, 네트워크 불필요)
"""
import sys
import os
import json
import datetime as dt

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
FIX = os.path.join(HERE, 'fixtures')

import macro_data as md
from macro_data import (
    MacroError, US_SERIES, KR_SERIES,
    parse_fred_observations, parse_ecos_rows, normalize_ecos_time,
    value_asof, shift_months, derive_metrics, sanity_warnings,
    build_snapshot, render_table,
)

_passed = 0
_failed = []


def eq(actual, expected, name):
    global _passed
    if actual == expected:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected}\n      실제: {actual}")


def close(actual, expected, name, tol=0.01):
    global _passed
    if actual is not None and abs(actual - expected) <= tol:
        _passed += 1
    else:
        _failed.append(f"{name}\n      기대: {expected} (+-{tol})\n      실제: {actual}")


def truthy(actual, name):
    eq(bool(actual), True, name)


def falsy(actual, name):
    eq(bool(actual), False, name)


def raises(fn, reason, name):
    """MacroError 를 정확한 reason 으로 던지는지."""
    global _passed
    try:
        fn()
    except MacroError as e:
        if e.reason == reason:
            _passed += 1
        else:
            _failed.append(f"{name}\n      기대 reason: {reason}\n      실제 reason: {e.reason}")
        return
    except Exception as e:
        _failed.append(f"{name}\n      기대: MacroError({reason})\n      실제: {type(e).__name__}: {e}")
        return
    _failed.append(f"{name}\n      기대: MacroError({reason})\n      실제: 예외 없음")


def fix(fname):
    with open(os.path.join(FIX, fname), encoding='utf-8') as f:
        return json.load(f)


# ============================================================================
# 1. FRED 파싱
# ============================================================================
raw10 = fix('fred_DGS10.json')
obs10 = parse_fred_observations(raw10)

truthy(obs10, 'FRED DGS10 파싱 결과 비어있지 않음')
eq(obs10[-1], ('2026-09-03', 4.77), 'FRED 최신 관측치 = 2026-09-03 4.77%')
eq(obs10[0][0], '2025-06-02', 'FRED 첫 관측치 날짜')
eq(obs10 == sorted(obs10), True, 'FRED 관측치는 날짜 오름차순')
# 원본 329건 중 휴일 '.' 13건은 제외돼야 한다
eq(len(obs10), len(raw10['observations']) - 13, "FRED '.' (휴일) 관측치 13건 제외")
eq(all(isinstance(v, float) for _, v in obs10), True, 'FRED 값은 float')

# 실패를 실패라고 말하는가
raises(lambda: parse_fred_observations(fix('fred_error.json')), 'api_error',
       'FRED error_message 응답 -> api_error')
raises(lambda: parse_fred_observations({'observations': []}), 'no_data',
       'FRED 관측치 0개 -> no_data (성공으로 오인 금지)')
raises(lambda: parse_fred_observations(
    {'observations': [{'date': '2026-01-01', 'value': '.'},
                      {'date': '2026-01-02', 'value': '.'}]}), 'no_data',
       "FRED 전부 '.' -> no_data")
raises(lambda: parse_fred_observations({}), 'bad_schema',
       'FRED observations 키 없음 -> bad_schema')
raises(lambda: parse_fred_observations('<html>error</html>'), 'bad_schema',
       'FRED 응답이 dict 가 아님 -> bad_schema')


# ============================================================================
# 2. ECOS 파싱 -- HTTP 200 인데 본문이 에러인 함정
# ============================================================================
rawbr = fix('ecos_722Y001_base_rate.json')
obsbr = parse_ecos_rows(rawbr, stat_code='722Y001')

eq(obsbr[0], ('2024-01-01', 3.5), 'ECOS 기준금리 첫 관측치 (202401 -> 2024-01-01)')
eq(obsbr[-1], ('2026-08-01', 3.0), 'ECOS 기준금리 최신 관측치 (202608 -> 3.0%)')
eq(len(obsbr), len(rawbr['StatisticSearch']['row']), 'ECOS 행 수 보존')
eq(obsbr == sorted(obsbr), True, 'ECOS 관측치는 날짜 오름차순')

obsfx = parse_ecos_rows(fix('ecos_731Y001_usdkrw.json'), stat_code='731Y001')
eq(obsfx[-1], ('2026-09-07', 1355.2), 'ECOS 원/달러 최신 (일별 20260907 -> 2026-09-07)')

# HTTP 200 + RESULT 블록 = 실패
raises(lambda: parse_ecos_rows(fix('ecos_error.json')), 'api_error',
       'ECOS RESULT 블록 (HTTP 200) -> api_error')
try:
    parse_ecos_rows(fix('ecos_error.json'))
except MacroError as e:
    eq(e.as_dict().get('code'), 'INFO-200', 'ECOS 실패 진단에 RESULT.CODE 보존')
    truthy(e.as_dict().get('message'), 'ECOS 실패 진단에 메시지 보존')

raises(lambda: parse_ecos_rows({'RESULT': {'CODE': 'INFO-100', 'MESSAGE': '인증키가 유효하지 않습니다.'}}),
       'api_error', 'ECOS 인증키 오류 (HTTP 200) -> api_error')
raises(lambda: parse_ecos_rows({'StatisticSearch': {'list_total_count': 0, 'row': []}}), 'no_data',
       'ECOS 행 0개 -> no_data')
raises(lambda: parse_ecos_rows({}), 'bad_schema', 'ECOS StatisticSearch 키 없음 -> bad_schema')
raises(lambda: parse_ecos_rows(rawbr, stat_code='999Y999'), 'wrong_series',
       'ECOS 요청 통계표코드와 응답 STAT_CODE 불일치 -> wrong_series')

# 값이 결측이거나 문자열인 행은 건너뛴다
mixed = {'StatisticSearch': {'row': [
    {'STAT_CODE': 'X', 'TIME': '202601', 'DATA_VALUE': '1.5'},
    {'STAT_CODE': 'X', 'TIME': '202602', 'DATA_VALUE': ''},
    {'STAT_CODE': 'X', 'TIME': '202603', 'DATA_VALUE': None},
    {'STAT_CODE': 'X', 'TIME': '202604', 'DATA_VALUE': '2.0'},
]}}
eq(parse_ecos_rows(mixed), [('2026-01-01', 1.5), ('2026-04-01', 2.0)], 'ECOS 결측값 행 제외')


# ============================================================================
# 3. 시간 정규화 / 조회 헬퍼
# ============================================================================
eq(normalize_ecos_time('20260907'), '2026-09-07', 'ECOS 일별 TIME 정규화')
eq(normalize_ecos_time('202608'), '2026-08-01', 'ECOS 월별 TIME 정규화')
eq(normalize_ecos_time('2026Q3'), '2026-07-01', 'ECOS 분기 TIME 정규화')
eq(normalize_ecos_time('2026'), '2026-01-01', 'ECOS 연별 TIME 정규화')

eq(shift_months('2026-09-03', -3), '2026-06-03', 'shift_months -3')
eq(shift_months('2026-09-03', -12), '2025-09-03', 'shift_months -12')
eq(shift_months('2026-03-31', -1), '2026-02-28', 'shift_months 말일 보정 (2026-02 은 28일)')

series = [('2026-01-05', 1.0), ('2026-02-10', 2.0), ('2026-03-20', 3.0)]
eq(value_asof(series, '2026-02-10'), ('2026-02-10', 2.0), 'value_asof 정확히 일치')
eq(value_asof(series, '2026-03-01'), ('2026-02-10', 2.0), 'value_asof 공백(주말/휴일) 시 직전값')
eq(value_asof(series, '2026-12-31'), ('2026-03-20', 3.0), 'value_asof 미래 지정 시 마지막값')
eq(value_asof(series, '2025-12-31'), None, 'value_asof 시계열 시작 이전 -> None')
eq(value_asof([], '2026-01-01'), None, 'value_asof 빈 시계열 -> None')


# ============================================================================
# 4. 파생지표 (3개월/12개월 변화)
# ============================================================================
spec_diff = {'label': '테스트금리', 'unit': '%', 'freq': 'D', 'change_mode': 'diff',
             'sane': (-1.0, 25.0)}
spec_pct = {'label': '테스트지수', 'unit': 'pt', 'freq': 'D', 'change_mode': 'pct',
            'sane': (0.0, 1000.0)}

m = derive_metrics(obs10, spec_diff, asof='2026-09-03')
eq(m['latest'], 4.77, '파생: 최신값')
eq(m['latest_date'], '2026-09-03', '파생: 최신 날짜')
# 3개월 전(2026-06-03) / 12개월 전(2025-09-03) 값을 픽스처에서 독립 계산해 대조
raw_map = {o['date']: o['value'] for o in raw10['observations'] if o['value'] != '.'}
eq(m['date_3m_ago'], '2026-06-03', '파생: 3개월 전 기준일')
eq(m['value_3m_ago'], float(raw_map['2026-06-03']), '파생: 3개월 전 값 (원본 대조)')
close(m['change_3m'], round(4.77 - float(raw_map['2026-06-03']), 4), '파생: 3개월 변화 (diff, %p)')
eq(m['date_12m_ago'], '2025-09-03', '파생: 12개월 전 기준일')
close(m['change_12m'], round(4.77 - float(raw_map['2025-09-03']), 4), '파생: 12개월 변화 (diff, %p)')
eq(m['change_unit'], '%p', "파생: diff 모드 변화 단위는 '%p'")
eq(m['obs_count'], len(obs10), '파생: 관측치 개수 기록')

syn = [('2025-09-03', 100.0), ('2026-06-03', 110.0), ('2026-09-03', 121.0)]
mp = derive_metrics(syn, spec_pct, asof='2026-09-03')
close(mp['change_3m'], 10.0, '파생: pct 모드 3개월 +10%')
close(mp['change_12m'], 21.0, '파생: pct 모드 12개월 +21%')
eq(mp['change_unit'], '%', "파생: pct 모드 변화 단위는 '%'")

# CPI 는 지수라서 전년비(YoY) 를 별도 필드로 낸다
cpi_obs = parse_fred_observations(fix('fred_CPIAUCSL.json'))
cpi_spec = dict(US_SERIES['cpi'])
mc = derive_metrics(cpi_obs, cpi_spec, asof='2026-09-07')
eq(mc['latest_date'], '2026-07-01', 'CPI 최신 관측 월 (월별 시계열)')
close(mc['latest'], 332.813, 'CPI 최신 지수값', tol=0.001)
truthy('yoy' in mc, 'CPI 는 yoy 필드를 낸다')
cpi_map = {o['date']: float(o['value']) for o in fix('fred_CPIAUCSL.json')['observations']
           if o['value'] != '.'}
close(mc['yoy'], (332.813 / cpi_map['2025-07-01'] - 1) * 100, 'CPI YoY = 12개월 전 지수 대비 %', tol=0.01)

# 12개월 데이터가 없으면 조용히 0 으로 채우지 말고 None 을 남긴다
short = [('2026-08-01', 5.0), ('2026-09-01', 5.5)]
ms = derive_metrics(short, spec_diff, asof='2026-09-01')
eq(ms['change_12m'], None, '12개월 전 데이터 없으면 change_12m = None (0 으로 위조 금지)')
eq(ms['value_12m_ago'], None, '12개월 전 값 없으면 None')

raises(lambda: derive_metrics([], spec_diff, asof='2026-09-01'), 'no_data',
       '빈 시계열로 파생 계산 시도 -> no_data')


# ============================================================================
# 5. 이상치 / 신선도 경고
# ============================================================================
w = sanity_warnings('ust10y', {'latest': -3.0, 'latest_date': '2026-09-03'}, spec_diff, asof='2026-09-03')
truthy(any('범위' in x for x in w), '금리 음수 -> 이상치 경고')
w = sanity_warnings('ust10y', {'latest': 140.0, 'latest_date': '2026-09-03'}, spec_diff, asof='2026-09-03')
truthy(any('범위' in x for x in w), '금리 100 초과 -> 이상치 경고')
w = sanity_warnings('ust10y', {'latest': 4.77, 'latest_date': '2026-09-03'}, spec_diff, asof='2026-09-03')
eq(w, [], '정상 범위 -> 경고 없음')

# 신선도: 일별 시계열이 한참 멈춰 있으면 경고 (URL 이전으로 죽은 소스 탐지)
w = sanity_warnings('ust10y', {'latest': 4.77, 'latest_date': '2026-01-03'}, spec_diff, asof='2026-09-03')
truthy(any('지연' in x or '오래' in x for x in w), '일별 시계열 8개월 정체 -> 신선도 경고')
spec_m = {'label': 'CPI', 'unit': 'idx', 'freq': 'M', 'change_mode': 'pct', 'sane': (0.0, 1000.0)}
w = sanity_warnings('cpi', {'latest': 332.8, 'latest_date': '2026-07-01'}, spec_m, asof='2026-09-07')
eq(w, [], '월별 시계열 2개월 시차는 정상 (경고 없음)')

# 게시 주기가 느린 시리즈는 spec 에서 신선도 기준을 늘릴 수 있다
# (DTWEXBGS 달러인덱스는 일별인데 FRED 게시가 주 1회라 10일 기준이면 매주 거짓 경고)
spec_slow = dict(spec_diff, stale_days=21)
w = sanity_warnings('dollar_index', {'latest': 4.0, 'latest_date': '2026-08-28'},
                    spec_slow, asof='2026-09-08')
eq(w, [], 'stale_days 오버라이드 시 11일 지연은 경고 없음')
w = sanity_warnings('dollar_index', {'latest': 4.0, 'latest_date': '2026-07-01'},
                    spec_slow, asof='2026-09-08')
truthy(any('지연' in x for x in w), 'stale_days 오버라이드해도 69일 지연은 경고')
eq(US_SERIES['dollar_index'].get('stale_days'), 21,
   'US dollar_index 는 주 1회 게시라 stale_days=21')


# ============================================================================
# 6. 스냅샷 조립 -- 주입 fetch 로 네트워크 없이
# ============================================================================
FIXTURE_BY_ALIAS = {
    'ust10y': 'fred_DGS10.json',
    'cpi': 'fred_CPIAUCSL.json',
}


def fake_fetch_us(alias, spec):
    if alias in FIXTURE_BY_ALIAS:
        return fix(FIXTURE_BY_ALIAS[alias])
    raise MacroError('network', '테스트용 강제 네트워크 실패',
                     series_id=spec.get('series_id'), status=None, length=0)


md.LAST_ERRORS.clear()
snap = build_snapshot('US', aliases=['ust10y', 'cpi', 'vix'], fetch=fake_fetch_us, asof='2026-09-07')

eq(snap['country'], 'US', '스냅샷 country')
truthy(snap.get('_collected_at'), '스냅샷에 _collected_at 필수')
truthy('warnings' in snap, '스냅샷에 warnings 필수')
eq(snap['series']['ust10y']['latest'], 4.77, '스냅샷 ust10y 최신값')
eq(snap['series']['ust10y']['ok'], True, '스냅샷 성공 시리즈는 ok=True')
truthy(snap['series']['ust10y'].get('label'), '스냅샷 시리즈에 한글 라벨')
truthy(snap['series']['ust10y'].get('source'), '스냅샷 시리즈에 출처 표기')

# 실패한 시리즈는 조용히 사라지지 않고 이유와 함께 남는다
truthy('vix' in snap['series'], '실패 시리즈도 결과에 남는다 (조용히 누락 금지)')
eq(snap['series']['vix']['ok'], False, '실패 시리즈 ok=False')
eq(snap['series']['vix']['error']['reason'], 'network', '실패 시리즈에 실패 사유 기록')
truthy(any('vix' in x for x in snap['warnings']), '실패가 상위 warnings 에도 올라온다')
truthy(md.LAST_ERRORS, '실패가 모듈 전역 LAST_ERRORS 에 축적된다')
eq(snap['ok_count'], 2, '스냅샷 성공 개수')
eq(snap['fail_count'], 1, '스냅샷 실패 개수')
eq(snap['ok'], False, '하나라도 실패하면 스냅샷 ok=False')

# 관측치 0개 응답도 실패로 처리 (성공한 척 금지)
def empty_fetch(alias, spec):
    return {'observations': []}


snap2 = build_snapshot('US', aliases=['ust10y'], fetch=empty_fetch, asof='2026-09-07')
eq(snap2['series']['ust10y']['ok'], False, '관측치 0개 응답 -> 실패 처리')
eq(snap2['series']['ust10y']['error']['reason'], 'no_data', '관측치 0개 -> no_data 기록')
eq(snap2['ok'], False, '전건 실패 스냅샷 ok=False')

# JSON 직렬화 가능해야 파일로 남길 수 있다
truthy(json.dumps(snap, ensure_ascii=False, default=str), '스냅샷 JSON 직렬화 가능')

# 부분 조회는 subset=True 로 표시되어 전체 스냅샷 파일을 덮어쓰지 않는다
eq(snap['subset'], True, '일부 지표만 조회하면 subset=True')
full = build_snapshot('US', fetch=fake_fetch_us, asof='2026-09-07')
eq(full['subset'], False, '전체 조회면 subset=False')
eq(len(full['series']), len(US_SERIES), '전체 조회는 카탈로그 전건')
truthy(md.build_snapshot('US', aliases=['ust10y'], fetch=fake_fetch_us,
                         asof='2026-09-07')['subset'], '단건 조회도 subset=True')

# save_snapshot 은 지정 경로에 원자적으로 쓰고 다시 읽힌다
import tempfile
with tempfile.TemporaryDirectory() as td:
    sp = md.save_snapshot(snap, os.path.join(td, 'sub', '_macro_test.json'))
    truthy(os.path.exists(sp), 'save_snapshot 파일 생성 (하위 폴더 자동 생성)')
    back = json.load(open(sp, encoding='utf-8'))
    eq(back['series']['ust10y']['latest'], 4.77, '저장 후 재로드 값 보존')
    truthy(back.get('_collected_at'), '저장본에 _collected_at 보존')
    falsy(os.path.exists(sp + '.tmp'), '임시 파일이 남지 않음')

# 알 수 없는 별칭은 조용히 무시하지 않고 즉시 에러
try:
    build_snapshot('US', aliases=['ust10y', '없는지표'], fetch=fake_fetch_us)
    _failed.append('알 수 없는 별칭 -> ValueError (실제: 예외 없음)')
except ValueError:
    _passed += 1
try:
    build_snapshot('JP', fetch=fake_fetch_us)
    _failed.append('지원하지 않는 country -> ValueError (실제: 예외 없음)')
except ValueError:
    _passed += 1


# ============================================================================
# 7. KR 스냅샷 (ECOS 픽스처)
# ============================================================================
KR_FIX = {
    'base_rate': 'ecos_722Y001_base_rate.json',
    'cpi': 'ecos_901Y009_cpi.json',
    'usdkrw': 'ecos_731Y001_usdkrw.json',
}


def fake_fetch_kr(alias, spec):
    if alias in KR_FIX:
        return fix(KR_FIX[alias])
    raise MacroError('http_status', 'ECOS 500', status=500, length=0)


ksnap = build_snapshot('KR', aliases=['base_rate', 'cpi', 'usdkrw', 'ktb3y'],
                       fetch=fake_fetch_kr, asof='2026-09-07')
eq(ksnap['country'], 'KR', 'KR 스냅샷 country')
eq(ksnap['series']['base_rate']['latest'], 3.0, 'KR 기준금리 3.00%')
eq(ksnap['series']['usdkrw']['latest'], 1355.2, 'KR 원/달러 1355.2')
kcpi_rows = fix('ecos_901Y009_cpi.json')['StatisticSearch']['row']
kmap = {r['TIME']: float(r['DATA_VALUE']) for r in kcpi_rows}
close(ksnap['series']['cpi']['yoy'], (kmap['202608'] / kmap['202508'] - 1) * 100,
      'KR CPI YoY = 전년동월 대비 %', tol=0.01)
eq(ksnap['series']['ktb3y']['ok'], False, 'KR 실패 시리즈 ok=False')
eq(ksnap['series']['ktb3y']['error']['reason'], 'http_status', 'KR 실패 사유 보존')

# 시리즈 정의 자체 검증
for name, table in (('US_SERIES', US_SERIES), ('KR_SERIES', KR_SERIES)):
    for alias, spec in table.items():
        truthy(spec.get('label'), f'{name}.{alias} label 정의')
        truthy(spec.get('unit'), f'{name}.{alias} unit 정의')
        eq(spec.get('change_mode') in ('diff', 'pct'), True, f'{name}.{alias} change_mode 정의')
        eq(len(spec.get('sane', ())), 2, f'{name}.{alias} sane 범위 정의')
        eq(spec.get('freq') in ('D', 'M'), True, f'{name}.{alias} freq 정의')

for need in ['policy_rate', 'ust10y', 'ust2y', 'yield_spread', 'cpi', 'unemployment',
             'dollar_index', 'wti', 'vix']:
    truthy(need in US_SERIES, f'US_SERIES 필수 지표 {need}')
for need in ['base_rate', 'usdkrw', 'cpi', 'ktb3y']:
    truthy(need in KR_SERIES, f'KR_SERIES 필수 지표 {need}')


# ============================================================================
# 8. 콘솔 출력 -- cp949 안전 (em-dash/이모지 금지)
# ============================================================================
table = render_table(snap)
truthy(table, 'render_table 출력 존재')
truthy('4.77' in table, 'render_table 에 실측값 표시')
truthy('vix' in table or 'VIX' in table, 'render_table 에 실패 시리즈도 표시')
eq('—' in table or '–' in table, False, 'render_table em-dash/en-dash 금지')
try:
    table.encode('cp949')
    _passed += 1
except UnicodeEncodeError as e:
    _failed.append(f'render_table cp949 인코딩 가능 (Windows 콘솔)\n      실제: {e}')

ktable = render_table(ksnap)
try:
    ktable.encode('cp949')
    _passed += 1
except UnicodeEncodeError as e:
    _failed.append(f'render_table(KR) cp949 인코딩 가능\n      실제: {e}')


# ============================================================================
# 9. 네트워크 실측 (--net)
# ============================================================================
def net_tests():
    print('  [net] FRED / ECOS 실호출...')
    us = build_snapshot('US')
    print(f"    US: ok={us['ok_count']}/{us['ok_count'] + us['fail_count']}")
    truthy(us['ok_count'] >= 7, '[net] US 9개 중 7개 이상 성공')
    t = us['series'].get('ust10y', {})
    truthy(t.get('ok'), '[net] US 10년물 조회 성공')
    truthy(0 < (t.get('latest') or -1) < 25, '[net] US 10년물 값 상식 범위')
    for a, s in us['series'].items():
        if not s['ok']:
            print(f"    [FAIL] {a}: {s['error']}")

    kr = build_snapshot('KR')
    print(f"    KR: ok={kr['ok_count']}/{kr['ok_count'] + kr['fail_count']}")
    for a, s in kr['series'].items():
        if not s['ok']:
            print(f"    [FAIL] {a}: {s['error']}")
    truthy(kr['ok_count'] >= 3, '[net] KR 4개 중 3개 이상 성공')
    fx = kr['series'].get('usdkrw', {})
    truthy(900 < (fx.get('latest') or 0) < 2000, '[net] 원/달러 값 상식 범위')


# ============================================================================
if __name__ == '__main__':
    if '--net' in sys.argv:
        net_tests()

    print(f"\n  테스트: {_passed}/{_passed + len(_failed)} 통과")
    if _failed:
        print('\n  [실패]')
        for f in _failed:
            print(f'    - {f}')
        sys.exit(1)
    sys.exit(0)
