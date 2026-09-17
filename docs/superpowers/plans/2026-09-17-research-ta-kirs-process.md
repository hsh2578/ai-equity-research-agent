# /research-ta IR협의회 작성 과정 반영 -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** IR협의회 리포트 22편 역분석(재료 비중·섹션 순서)에 맞춰 `/research-ta` 의 수집·게이트·요약 형식을 바꾼다.

**Architecture:** 결정론 수집기 3개(`ta_trade_stats` 관세청 수출입 / `ta_customer_docs` 고객사·장비사 공개자료 / `ta_company_voice` 회사 IR·인터뷰)를 `data/{종목}/ta/` 에 쓰고, 검증기 1개(`ta_industry_gate`)가 산업현황 분량·회사 밖 비율·출처 종류와 요약 ■3·판단 블록 분리를 검사한다. 기존 래퍼(`sec_edgar`, `dart_api`, `ta_common`)를 재사용하고 새 의존성은 없다. 커맨드 문서와 brief 형식만 고친다.

**Tech Stack:** Python 3 stdlib(`urllib`, `xml.etree`, `re`, `json`, `subprocess`), 기존 `requests` 래퍼, `yt-dlp`(설치됨, 선택).

**Spec:** `docs/research-ta/kirs-construction.md` 7절 (근거는 5·6절).

## Global Constraints
- 새 도구는 테스트 동반. 테스트는 `tests/test_*.py` 파일 하나, 네트워크·파일 I/O 없이 순수 함수 픽스처로, `tests/run_all.py` 가 자동 발견(파일명 `test_` 접두).
- 콘솔 출력에 em-dash·이모지 금지(cp949). `sys.stdout` UTF-8 강제 헤더 사용.
- `except Exception: return None` 금지 -- 실패 사유를 `ta/manifest.json` 에 `manifest_update(stock, step, 'failed', reason=...)` 로 남긴다.
- API 키는 `env_loader.load_env()` 로만(신규 발급 금지). `DATA_GO_KR_API_KEY` 보유.
- 임시 파일은 `data/{종목}/ta/` 아래.
- 커밋은 사용자 확인 후(공개 레포). 아래 Step 의 `git commit` 은 사용자 승인 뒤에만 실행.

---

### Task 1: `ta_trade_stats.py` -- 관세청 품목별·국가별 수출입

**Files:**
- Create: `scripts/ta_trade_stats.py`
- Test: `tests/test_ta_trade_stats.py`

**Interfaces:**
- Consumes: `ta_common.ta_dir(stock)`, `ta_common.manifest_update`, `data/{종목}/ta/trade_query.json` (메인이 STEP 1 에서 사업보고서 II장을 보고 쓴다: `{"hs": ["8486","3701"], "countries": ["CN","US","TW"], "months": 24}`)
- Produces: `data/{종목}/ta/trade_stats.json` = `{"asof", "query", "series": {hs: {country: [{"ym","exp_usd","imp_usd"}]}}, "yoy": {hs: {country: {"exp_ttm","exp_ttm_prev","yoy"}}}, "failed": [...]}`
- 순수 함수 `parse_items(xml_text) -> list[dict]`, `ttm_yoy(rows, end_ym) -> dict`

- [ ] **Step 1: 실패하는 테스트**

```python
"""ta_trade_stats 테스트. 관세청 XML 파싱과 TTM/YoY 계산만(네트워크 없음). 실행: python tests/test_ta_trade_stats.py"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_trade_stats as t  # noqa: E402
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
_passed, _failed = 0, []
def eq(got, want, label):
    global _passed
    if got == want: _passed += 1
    else: _failed.append((label, want, got))

XML = '''<?xml version="1.0"?><response><header><resultCode>00</resultCode></header><body><items>
<item><expDlr>1744440255</expDlr><impDlr>174193205</impDlr><hsCd>-</hsCd><statCd>-</statCd><year>총계</year></item>
<item><expDlr>852533</expDlr><impDlr>3068</impDlr><hsCd>848610</hsCd><statCd>CN</statCd><year>2026.01</year></item>
<item><expDlr>900000</expDlr><impDlr>1000</impDlr><hsCd>848610</hsCd><statCd>CN</statCd><year>2026.02</year></item>
</items></body></response>'''
rows = t.parse_items(XML)
eq(len(rows), 2, '총계 행 제외')
eq(rows[0], {'ym': '202601', 'hs': '848610', 'country': 'CN', 'exp_usd': 852533, 'imp_usd': 3068}, '행 파싱')

# TTM/YoY: 24개월 시계열
series = [{'ym': f'{2024 + (i // 12)}{i % 12 + 1:02d}', 'exp_usd': 100 + i, 'imp_usd': 0} for i in range(24)]
y = t.ttm_yoy(series, '202512')
eq(y['exp_ttm'], sum(100 + i for i in range(12, 24)), '최근 12개월 합')
eq(y['exp_ttm_prev'], sum(100 + i for i in range(0, 12)), '직전 12개월 합')
eq(round(y['yoy'], 4), round(y['exp_ttm'] / y['exp_ttm_prev'] - 1, 4), 'yoy')
eq(t.ttm_yoy(series[:6], '202512'), None, '표본 부족이면 None')

print(f'ta_trade_stats 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for l, w, g in _failed: print(f'  [FAIL] {l}: want={w!r} got={g!r}')
sys.exit(1 if _failed else 0)
```

- [ ] **Step 2: 실패 확인** -- `python tests/test_ta_trade_stats.py` -> `ModuleNotFoundError: ta_trade_stats`

- [ ] **Step 3: 구현**

```python
# -*- coding: utf-8 -*-
"""관세청 품목별·국가별 수출입 실적 (data.go.kr 1220000/nitemtrade) -> data/{종목}/ta/trade_stats.json
IR협의회 산업현황 재료의 44%가 협회·정부 통계이고 그중 관세청이 가장 잦다(docs/research-ta/kirs-construction.md 2절).
입력: ta/trade_query.json {"hs": [...4~10자리], "countries": [...ISO2], "months": 24}
usage: python scripts/ta_trade_stats.py {종목명}
"""
import io, json, os, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:/Users/hsh/Desktop'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_loader import load_env  # noqa: E402
from ta_common import ta_dir, manifest_update, write_json, read_json  # noqa: E402
URL = 'https://apis.data.go.kr/1220000/nitemtrade/getNitemtradeList'


def parse_items(xml_text):
    """총계 행(year='총계')을 빼고 [{'ym','hs','country','exp_usd','imp_usd'}]."""
    root = ET.fromstring(xml_text)
    out = []
    for it in root.iter('item'):
        g = lambda k: (it.findtext(k) or '').strip()  # noqa: E731
        if g('hsCd') in ('', '-') or g('statCd') in ('', '-'):
            continue
        out.append({'ym': g('year').replace('.', ''), 'hs': g('hsCd'), 'country': g('statCd'),
                    'exp_usd': int(g('expDlr') or 0), 'imp_usd': int(g('impDlr') or 0)})
    return out


def ttm_yoy(series, end_ym):
    """end_ym 까지 최근 12개월 수출 합과 직전 12개월 합. 24개월 미만이면 None."""
    rows = sorted((r for r in series if r['ym'] <= end_ym), key=lambda r: r['ym'])[-24:]
    if len(rows) < 24:
        return None
    cur, prev = sum(r['exp_usd'] for r in rows[12:]), sum(r['exp_usd'] for r in rows[:12])
    return {'exp_ttm': cur, 'exp_ttm_prev': prev, 'yoy': (cur / prev - 1) if prev else None}


def fetch(hs, country, start_ym, end_ym, key):
    q = urllib.parse.urlencode({'serviceKey': key, 'strtYymm': start_ym, 'endYymm': end_ym, 'hsSgn': hs, 'cntyCd': country})
    with urllib.request.urlopen(URL + '?' + q, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')


def main(argv=None):
    stock = (argv or sys.argv[1:])[0]
    load_env(); key = os.environ.get('DATA_GO_KR_API_KEY')
    d = ta_dir(stock); q = read_json(os.path.join(d, 'trade_query.json'))
    if not key or not q:
        manifest_update(stock, 'trade_stats', 'failed', reason='키 또는 trade_query.json 없음'); print('[FAIL] 키/쿼리 없음'); return 1
    today = date.today(); months = int(q.get('months', 24)) + 1
    end_ym = f'{today.year}{today.month:02d}'
    sy, sm = today.year, today.month - months
    while sm <= 0: sy, sm = sy - 1, sm + 12
    out = {'asof': today.isoformat(), 'query': q, 'series': {}, 'yoy': {}, 'failed': []}
    for hs in q['hs']:
        for c in q['countries']:
            try:
                rows = parse_items(fetch(hs, c, f'{sy}{sm:02d}', end_ym, key))
            except Exception as e:  # 실패 이유를 남긴다(조용한 실패 금지)
                out['failed'].append({'hs': hs, 'country': c, 'reason': repr(e)[:200]}); continue
            # 응답 검증: 요청한 hs 로 시작하는 행만 (구 FnGuide 사고: 무엇을 넣어도 같은 페이지)
            rows = [r for r in rows if r['hs'].startswith(hs)]
            agg = {}
            for r in rows:
                a = agg.setdefault(r['ym'], {'ym': r['ym'], 'exp_usd': 0, 'imp_usd': 0}); a['exp_usd'] += r['exp_usd']; a['imp_usd'] += r['imp_usd']
            ser = sorted(agg.values(), key=lambda r: r['ym'])
            out['series'].setdefault(hs, {})[c] = ser
            y = ttm_yoy(ser, ser[-1]['ym']) if ser else None
            out['yoy'].setdefault(hs, {})[c] = y
    write_json(os.path.join(d, 'trade_stats.json'), out)
    status = 'ok' if out['series'] else 'failed'
    manifest_update(stock, 'trade_stats', status, hs=len(q['hs']), failed=len(out['failed']))
    print(f"[{status.upper()}] trade_stats: {sum(len(v) for v in out['series'].values())} 시리즈, 실패 {len(out['failed'])}")
    return 0 if status == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과 확인** -- `python tests/test_ta_trade_stats.py` -> `5개 통과 / 0개 실패`
- [ ] **Step 5: 실종목 1회** -- `data/에프에스티/ta/trade_query.json` 에 `{"hs":["3701","8486"],"countries":["CN","US","TW","JP"],"months":24}` 를 쓰고 `python scripts/ta_trade_stats.py 에프에스티`. `trade_stats.json` 의 시리즈 길이 25, `failed` 0 확인. 두 HS 의 값이 서로 다른지 확인(응답 검증).
- [ ] **Step 6: Commit (사용자 승인 후)** -- `git add scripts/ta_trade_stats.py tests/test_ta_trade_stats.py && git commit -m "feat(research-ta): ta_trade_stats -- 관세청 품목별 국가별 수출입 (IR협의회 산업현황 재료)"`

---

### Task 2: `ta_customer_docs.py` -- 고객사·장비사·경쟁사 공개 자료

**Files:**
- Create: `scripts/ta_customer_docs.py`
- Test: `tests/test_ta_customer_docs.py`

**Interfaces:**
- Consumes: `data/{종목}/ta/customers.json` (메인이 STEP 1 에 쓴다): `[{"name":"Lam Research","kind":"US","ticker":"LRCX","keywords":["capex","Korea","memory"]},{"name":"삼성전자","kind":"KR","keywords":["시설투자","평택","P4"]}]`; `sec_edgar.get_cik/get_recent_filings` + 본문 텍스트(`sec_edgar` 의 문서 fetch 함수, 없으면 `requests.get(doc_url, headers=HEADERS)` + `html_to_text`); `dart_api.get_corp_code/download_report_document/html_to_text`, `collect_dart_filings.fetch_list`
- Produces: `data/{종목}/ta/customer_docs/{name}.md` (문단 인용 + `출처 file:line`), `data/{종목}/ta/customer_docs/index.json`
- 순수 함수 `pick_paragraphs(text, keywords, window=600, max_n=12) -> list[dict(line, quote)]`

- [ ] **Step 1: 실패하는 테스트**

```python
"""ta_customer_docs 테스트: 키워드 문단 추출만(네트워크 없음). 실행: python tests/test_ta_customer_docs.py"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_customer_docs as c  # noqa: E402
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
_passed, _failed = 0, []
def eq(got, want, label):
    global _passed
    if got == want: _passed += 1
    else: _failed.append((label, want, got))

TEXT = "line one\nWe expect capital expenditures of $4.0 billion in fiscal 2026.\nunrelated\n" + "x" * 50 + "\nOur Korea revenue grew 20% driven by memory customers.\nboilerplate forward-looking statements safe harbor\n"
hits = c.pick_paragraphs(TEXT, ['capex', 'capital expenditure', 'korea'], window=80, max_n=5)
eq([h['line'] for h in hits], [2, 5], '키워드 줄 번호(1-base), 중복 없이')
eq(hits[0]['quote'].startswith('We expect capital'), True, '인용은 원문 그대로')
eq(c.pick_paragraphs(TEXT, ['nothing']), [], '없으면 빈 리스트')
eq(len(c.pick_paragraphs("capex\n" * 100, ['capex'], max_n=3)), 3, 'max_n 상한')
eq(c.is_boilerplate('forward-looking statements safe harbor'), True, '보일러플레이트 제외')

print(f'ta_customer_docs 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for l, w, g in _failed: print(f'  [FAIL] {l}: want={w!r} got={g!r}')
sys.exit(1 if _failed else 0)
```

- [ ] **Step 2: 실패 확인** -- `python tests/test_ta_customer_docs.py` -> ModuleNotFoundError

- [ ] **Step 3: 구현**

```python
# -*- coding: utf-8 -*-
"""고객사·장비사·경쟁사 공개 자료 -> data/{종목}/ta/customer_docs/{name}.md
IR협의회 산업현황 재료의 22%가 고객사·경쟁사 공개자료(10-K/10-Q, 기업설명회 자료). 뉴스가 아니다.
입력: ta/customers.json [{"name","kind":"US"|"KR","ticker"|"corp","keywords":[...]}]
usage: python scripts/ta_customer_docs.py {종목명} [--max-filings 2]
"""
import io, json, os, re, sys
from datetime import date, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ta_common import ta_dir, manifest_update, read_json, write_json  # noqa: E402

BOILER = re.compile(r'forward-looking|safe harbor|투자판단 참고|본 자료는', re.I)


def is_boilerplate(line):
    return bool(BOILER.search(line))


def pick_paragraphs(text, keywords, window=600, max_n=12):
    """키워드가 든 줄(1-base)과 그 줄부터 window 자 인용. 보일러플레이트 줄 제외, 줄당 1회."""
    pat = re.compile('|'.join(re.escape(k) for k in keywords), re.I)
    lines = text.split('\n'); out = []
    for i, l in enumerate(lines, 1):
        if pat.search(l) and not is_boilerplate(l):
            out.append({'line': i, 'quote': '\n'.join(lines[i - 1:i + 3])[:window].strip()})
            if len(out) >= max_n:
                break
    return out


def us_docs(entry, max_filings):
    import sec_edgar as se
    cik = se.get_cik(entry['ticker']); docs = []
    for form in ('10-Q', '10-K'):
        for f in se.get_recent_filings(cik, form, max_filings):
            txt = se.get_filing_text(f) if hasattr(se, 'get_filing_text') else ''
            if txt:
                docs.append((f"SEC {form} {f.get('filingDate', '')}", txt))
    return docs


def kr_docs(entry, max_filings):
    from dart_api import get_corp_code, download_report_document, html_to_text
    from collect_dart_filings import fetch_list
    corp = get_corp_code(entry['name']); end = date.today(); bgn = end - timedelta(days=400)
    key = os.environ.get('DART_API_KEY'); docs = []
    for it in fetch_list(corp, bgn.strftime('%Y%m%d'), end.strftime('%Y%m%d'), key):
        nm = it.get('report_nm', '')
        if '기업설명회' in nm or '분기보고서' in nm or '반기보고서' in nm:
            for fn, html in (download_report_document(it['rcept_no']) or {}).items():
                docs.append((f"DART {nm} {it.get('rcept_dt', '')}", html_to_text(html)))
            if len(docs) >= max_filings:
                break
    return docs


def main(argv=None):
    a = argv or sys.argv[1:]; stock = a[0]
    max_f = int(a[a.index('--max-filings') + 1]) if '--max-filings' in a else 2
    sys.path.insert(0, r'C:/Users/hsh/Desktop'); from env_loader import load_env; load_env()
    d = ta_dir(stock); cust = read_json(os.path.join(d, 'customers.json')) or []
    out_dir = os.path.join(d, 'customer_docs'); os.makedirs(out_dir, exist_ok=True); index = []
    for e in cust:
        try:
            docs = us_docs(e, max_f) if e.get('kind') == 'US' else kr_docs(e, max_f)
        except Exception as ex:
            index.append({'name': e['name'], 'status': 'failed', 'reason': repr(ex)[:200]}); continue
        md = [f"# {e['name']} -- 공개 자료 발췌 ({date.today()})\n"]
        n = 0
        for label, txt in docs:
            raw = os.path.join(out_dir, re.sub(r'[^\w]+', '_', f"{e['name']}_{label}")[:80] + '.txt')
            open(raw, 'w', encoding='utf-8').write(txt)
            for h in pick_paragraphs(txt, e.get('keywords', [])):
                md.append(f"## {label} ({os.path.basename(raw)}:{h['line']})\n\n> {h['quote']}\n"); n += 1
        open(os.path.join(out_dir, f"{e['name']}.md"), 'w', encoding='utf-8').write('\n'.join(md))
        index.append({'name': e['name'], 'status': 'ok' if n else 'empty', 'quotes': n, 'docs': len(docs)})
    write_json(os.path.join(out_dir, 'index.json'), index)
    ok = sum(1 for i in index if i['status'] == 'ok')
    manifest_update(stock, 'customer_docs', 'ok' if ok else 'failed', ok=ok, total=len(index))
    print(f'[{"OK" if ok else "FAIL"}] customer_docs: {ok}/{len(index)} 고객사에서 인용 확보')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
```

`sec_edgar.get_filing_text` 가 없으면 이 Task 에서 `sec_edgar.py` 에 추가한다(기존 `requests.get(doc_url, headers=HEADERS)` + `html_to_text` 조합, 20줄 이내). 

- [ ] **Step 4: 테스트 통과** -- `python tests/test_ta_customer_docs.py` -> 5개 통과
- [ ] **Step 5: 실종목 1회** -- `data/에프에스티/ta/customers.json` 에 Lam Research(LRCX, US, ["capex","Korea","memory","WFE"]), 삼성전자(KR, ["시설투자","평택","테일러","P4"]) 를 넣고 실행. `customer_docs/index.json` 에 두 건 ok, md 파일에 `파일:줄` 출처 확인.
- [ ] **Step 6: Commit (사용자 승인 후)**

---

### Task 3: `ta_company_voice.py` -- 회사가 직접 말한 것 (IR 자료·인터뷰·IRTV)

**Files:**
- Create: `scripts/ta_company_voice.py`
- Test: `tests/test_ta_company_voice.py`

**Interfaces:**
- Consumes: `data/{종목}/ta/news.json`(기존 `ta_collect_news` 산출, `sources` 안 기사 목록에 `title`,`description`/`body`,`date`,`link`), DART 기업설명회 공시 첨부(`collect_dart_filings.fetch_list` + `download_report_document`), `yt-dlp`(선택: `--irtv` 플래그일 때 `ytsearch3:"IRTV {종목명}"` 자동자막)
- Produces: `data/{종목}/ta/company_voice.md` (섹션: IR 자료 발췌 / 인터뷰·발언 기사 / IRTV 자막 발췌, 각 인용에 출처·날짜), `company_voice.json`
- 순수 함수 `is_company_statement(title, body) -> bool`, `extract_statements(body, max_n=8) -> list[str]`

- [ ] **Step 1: 실패하는 테스트**

```python
"""ta_company_voice 테스트: 인터뷰·발언 기사 판별과 발언 문장 추출(네트워크 없음). 실행: python tests/test_ta_company_voice.py"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_company_voice as v  # noqa: E402
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
_passed, _failed = 0, []
def eq(got, want, label):
    global _passed
    if got == want: _passed += 1
    else: _failed.append((label, want, got))

eq(v.is_company_statement('[인터뷰] 에프에스티 대표 "내년 EUV 양산"', ''), True, '제목 인터뷰')
eq(v.is_company_statement('에프에스티, 카나투 장비 증설', '회사 관계자는 "3분기 양산"이라고 밝혔다.'), True, '본문 발언')
eq(v.is_company_statement('[특징주] 에프에스티 급등', '주가가 12% 올랐다.'), False, '반응 기사 제외')
eq(v.is_company_statement('에프에스티 목표주가 상향', '증권사는 매수 의견을 유지했다.'), False, '증권사 의견 제외')
body = '앞 문장. 장경빈 대표는 "인증은 연내 마무리"라고 말했다. 회사 측은 반응기 추가 발주를 밝혔다. 끝.'
eq(v.extract_statements(body), ['장경빈 대표는 "인증은 연내 마무리"라고 말했다.', '회사 측은 반응기 추가 발주를 밝혔다.'], '발언 문장만')
eq(v.extract_statements('아무 발언 없음.'), [], '없으면 빈 리스트')

print(f'ta_company_voice 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for l, w, g in _failed: print(f'  [FAIL] {l}: want={w!r} got={g!r}')
sys.exit(1 if _failed else 0)
```

- [ ] **Step 2: 실패 확인** -- ModuleNotFoundError

- [ ] **Step 3: 구현**

```python
# -*- coding: utf-8 -*-
"""회사가 직접 말한 것 -> data/{종목}/ta/company_voice.md
IR협의회 투자포인트 재료의 26%가 공시에 없는 '회사 설명'(램리서치 품목 승인 수, 초도 PO, 인증기간 단축).
우리는 회사 미팅이 없으므로 (1) DART 기업설명회 첨부 (2) 인터뷰·발언 기사 (3) IRTV 자막으로 대체한다.
usage: python scripts/ta_company_voice.py {종목명} [--irtv]
"""
import io, json, os, re, subprocess, sys, glob
from datetime import date, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ta_common import ta_dir, manifest_update, read_json, write_json, is_reaction_title  # noqa: E402

TITLE = re.compile(r'인터뷰|대표|CEO|회장|간담회|기업설명회|IR|밝혔|계획|전망')
SAY = re.compile(r'(대표|회장|사장|상무|이사|관계자|회사 측|회사측|동사)[^.。]{0,80}(밝혔|말했|설명했|강조했|언급했|전했|계획이라고|예정이라고)')
BROKER = re.compile(r'증권|목표주가|투자의견|리서치센터')


def is_company_statement(title, body):
    if is_reaction_title(title) or BROKER.search(title):
        return False
    return bool(TITLE.search(title) and not BROKER.search(body or '')) or bool(SAY.search(body or ''))


def extract_statements(body, max_n=8):
    sents = re.split(r'(?<=[.。])\s+', body or '')
    return [s.strip() for s in sents if SAY.search(s)][:max_n]


def news_statements(d):
    n = read_json(os.path.join(d, 'news.json')) or {}
    items = []
    for src in (n.get('sources') or {}).values():
        for a in (src.get('items') if isinstance(src, dict) else src) or []:
            t, b = a.get('title', ''), a.get('body') or a.get('description', '')
            if is_company_statement(t, b):
                items.append({'date': a.get('date') or a.get('pubDate', ''), 'title': t, 'link': a.get('link', ''), 'statements': extract_statements(b) or [t]})
    return sorted(items, key=lambda x: x['date'], reverse=True)[:30]


def ir_filings(stock, d):
    from dart_api import get_corp_code, download_report_document, html_to_text
    from collect_dart_filings import fetch_list
    key = os.environ.get('DART_API_KEY'); corp = get_corp_code(stock)
    end = date.today(); bgn = end - timedelta(days=730); out = []
    for it in fetch_list(corp, bgn.strftime('%Y%m%d'), end.strftime('%Y%m%d'), key):
        if '기업설명회' in it.get('report_nm', '') or '기업가치제고' in it.get('report_nm', ''):
            for fn, html in (download_report_document(it['rcept_no']) or {}).items():
                txt = html_to_text(html); p = os.path.join(d, f"_ir_{it['rcept_dt']}_{it['rcept_no']}.txt")
                open(p, 'w', encoding='utf-8').write(txt); out.append({'date': it['rcept_dt'], 'name': it['report_nm'], 'file': os.path.basename(p), 'chars': len(txt)})
    return out


def irtv(stock, d):
    """yt-dlp 로 IRTV 검색 상위 3건 자동자막(ko). 실패는 이유를 반환."""
    out_t = os.path.join(d, '_irtv_%(title)s.%(ext)s')
    r = subprocess.run(['yt-dlp', f'ytsearch3:IRTV {stock}', '--skip-download', '--write-auto-sub', '--sub-lang', 'ko', '--sub-format', 'vtt', '-o', out_t],
                       capture_output=True, text=True, timeout=180)
    files = glob.glob(os.path.join(d, '_irtv_*.vtt'))
    return {'files': [os.path.basename(f) for f in files], 'rc': r.returncode, 'err': r.stderr[-300:] if r.returncode else ''}


def main(argv=None):
    a = argv or sys.argv[1:]; stock = a[0]; use_irtv = '--irtv' in a
    sys.path.insert(0, r'C:/Users/hsh/Desktop'); from env_loader import load_env; load_env()
    d = ta_dir(stock); res = {'asof': date.today().isoformat(), 'news': news_statements(d), 'ir_filings': [], 'irtv': None, 'failed': []}
    try:
        res['ir_filings'] = ir_filings(stock, d)
    except Exception as e:
        res['failed'].append({'step': 'ir_filings', 'reason': repr(e)[:200]})
    if use_irtv:
        res['irtv'] = irtv(stock, d)
    md = [f'# {stock} -- 회사가 직접 말한 것 ({res["asof"]})\n', '## IR 자료(기업설명회 공시 첨부)\n']
    md += [f"- {f['date']} {f['name']} -> ta/{f['file']} ({f['chars']:,}자)" for f in res['ir_filings']] or ['- 없음']
    md += ['\n## 인터뷰·발언 기사\n']
    for it in res['news']:
        md.append(f"### {it['date']} {it['title']}\n" + '\n'.join(f'> {s}' for s in it['statements']) + f"\n{it['link']}\n")
    if res['irtv']:
        md += ['\n## IRTV 자막\n'] + [f'- ta/{f}' for f in res['irtv']['files']] + ([f"- 실패: {res['irtv']['err']}"] if res['irtv']['rc'] else [])
    open(os.path.join(d, 'company_voice.md'), 'w', encoding='utf-8').write('\n'.join(md))
    write_json(os.path.join(d, 'company_voice.json'), res)
    n = len(res['news']) + len(res['ir_filings'])
    manifest_update(stock, 'company_voice', 'ok' if n else 'failed', news=len(res['news']), ir=len(res['ir_filings']), failed=len(res['failed']))
    print(f"[{'OK' if n else 'FAIL'}] company_voice: 발언 기사 {len(res['news'])}, IR 첨부 {len(res['ir_filings'])}, 실패 {len(res['failed'])}")
    return 0 if n else 1


if __name__ == '__main__':
    sys.exit(main())
```

`news.json` 의 실제 키(`sources` 아래 구조)는 구현 전에 `python -c "import json;d=json.load(open('data/에프에스티/ta/news.json',encoding='utf-8'));print({k:type(v).__name__ for k,v in d['sources'].items()})"` 로 확인해 `news_statements` 의 순회를 맞춘다.

- [ ] **Step 4: 테스트 통과** -- 6개 통과
- [ ] **Step 5: 실종목 1회** -- `python scripts/ta_company_voice.py 에프에스티 --irtv`. `company_voice.md` 에 발언 기사 5건+ 확인, IR 첨부 유무, IRTV 자막 파일 유무(없으면 이유가 적혀 있어야 함).
- [ ] **Step 6: Commit (사용자 승인 후)**

---

### Task 4: `ta_industry_gate.py` -- 산업현황·요약·밸류 분리 검사

**Files:**
- Create: `scripts/ta_industry_gate.py`
- Test: `tests/test_ta_industry_gate.py`

**Interfaces:**
- Consumes: `scripts/analysis_{종목}_ta.json` (`meta.section_order`, `sections`, `opinion`, `meta.stock_name`)
- Produces: 콘솔 PASS/FAIL 표 + exit code. 순수 함수 `check(analysis: dict) -> list[dict(id, status, value, note)]`
- 검사 항목: **G1** 산업현황(s04) 분량 ≥ 본문의 20% / **G2** s04 회사 밖 비율 ≥ 90%(문단 단위: 종목명·"동사" 가 나오는 문단은 회사 안) / **G3** s04 출처 종류 ≥ 3(정규식: `협회|통계청|관세청|USITC|SEMI|SNE|TrendForce|IDC|10-K|10-Q|컨퍼런스콜|IR 자료|기업설명회`) / **G4** s01 `> **한 줄:**` 3개이고 ①에 숫자+`억원|%`, ②에 종목명 아닌 회사 실명(대문자 영문 또는 `전자|하이닉스|리서치` 등 후보 목록), ③에 연도·분기(`20\d\d|[1-4]Q|분기|하반기|상반기`) / **G5** s07 에 `밴드|Peer|비교기업` 이 있고 s01·s02 에 `SOTP|시나리오|DCF` 가 없다(밸류 분리) / **G6** 뉴스 재료 상한: s04 에 `보도|기사` ≤ 2회

- [ ] **Step 1: 실패하는 테스트**

```python
"""ta_industry_gate 테스트(픽스처 analysis dict, I/O 없음). 실행: python tests/test_ta_industry_gate.py"""
import io, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import ta_industry_gate as g  # noqa: E402
if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
_passed, _failed = 0, []
def eq(got, want, label):
    global _passed
    if got == want: _passed += 1
    else: _failed.append((label, want, got))

def fx(s04, s01, s07='밴드 대비 Peer 비교', s02='사건'):
    return {'meta': {'stock_name': '에프에스티', 'section_order': ['s01_opinion_thesis', 's04_industry_competition', 's02_thesis_catalysts', 's07_valuation']},
            'sections': {'s01_opinion_thesis': s01, 's04_industry_competition': s04, 's02_thesis_catalysts': s02, 's07_valuation': s07}}

good04 = ('관세청 통계에 따르면 8486 수출은 늘었다.\n\nSEMI 는 2027년 팹 투자를 전망했다.\n\n램리서치 10-K 는 capex 를 밝혔다.\n\n' * 3) + '에프에스티는 여기에 착지한다.'
good01 = '> **한 줄:** 상반기 영업이익 110억원\n\n> **한 줄:** 램리서치 벤더 등록\n\n> **한 줄:** 3Q26 양산 확인이 판정한다\n\n본문 ' + 'x' * 100
r = {c['id']: c for c in g.check(fx(good04, good01))}
eq(r['G1']['status'], 'PASS', 'G1 분량 20%+')
eq(r['G2']['status'], 'PASS', 'G2 회사밖 90%+')
eq(r['G3']['status'], 'PASS', 'G3 출처 3종+')
eq(r['G4']['status'], 'PASS', 'G4 요약 3불릿 형식')
eq(r['G5']['status'], 'PASS', 'G5 밸류 분리')
eq(r['G6']['status'], 'PASS', 'G6 뉴스 상한')
bad04 = '에프에스티는 동사의 펠리클을 판다. 보도에 따르면 기사에서 보도됐다.'
r2 = {c['id']: c for c in g.check(fx(bad04, '> **한 줄:** 하나뿐', s02='SOTP 시나리오'))}
eq([r2[k]['status'] for k in ('G1', 'G2', 'G3', 'G4', 'G5', 'G6')], ['FAIL'] * 6, '전부 FAIL')
eq(g.outside_ratio('에프에스티 문단.\n\n동사 문단.\n\n삼성전자 문단.\n\nSEMI 문단.', '에프에스티'), 0.5, '회사밖 비율 = 문단 기준')

print(f'ta_industry_gate 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
for l, w, gg in _failed: print(f'  [FAIL] {l}: want={w!r} got={gg!r}')
sys.exit(1 if _failed else 0)
```

- [ ] **Step 2: 실패 확인** -- ModuleNotFoundError

- [ ] **Step 3: 구현**

```python
# -*- coding: utf-8 -*-
"""IR협의회 구성 게이트 G1~G6 (docs/research-ta/kirs-construction.md 7절).
usage: python scripts/ta_industry_gate.py {종목명} [--analysis path]   (0 FAIL 필수)"""
import io, json, re, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SRC = re.compile(r'협회|통계청|관세청|USITC|SEMI|SNE|TrendForce|트렌드포스|IDC|Omdia|WSTS|10-K|10-Q|컨퍼런스콜|IR 자료|기업설명회|산업부|농림|식약처')
NEWS = re.compile(r'보도|기사')
MARGIN = re.compile(r'^> \*\*한 줄:\*\*\s*(.+)$', re.M)
NUM = re.compile(r'\d[\d,.]*\s*(억원|%|배|원)')
TIME = re.compile(r'20\d\d|[1-4]Q|분기|상반기|하반기|연내|내년')
NAME = re.compile(r'[A-Z][A-Za-z]{2,}|전자|하이닉스|리서치|테크|케미칼|머티리얼|화학|반도체|삼성|SK|LG|현대|TSMC|ASML')
VAL = re.compile(r'SOTP|시나리오|DCF|Bull|Bear')


def _body(a):
    s = a['sections']; return {k: s.get(k, '') for k in a['meta']['section_order'] if k in s}


def outside_ratio(text, name):
    paras = [p for p in re.split(r'\n\s*\n', text) if p.strip()]
    if not paras:
        return 0.0
    inside = sum(1 for p in paras if name in p or '동사' in p)
    return round(1 - inside / len(paras), 2)


def check(a):
    b = _body(a); name = a['meta']['stock_name']; s04 = b.get('s04_industry_competition', ''); s01 = b.get('s01_opinion_thesis', '')
    s07 = b.get('s07_valuation', ''); s02 = b.get('s02_thesis_catalysts', ''); tot = sum(len(v) for v in b.values()) or 1
    out = []
    share = len(s04) / tot; out.append({'id': 'G1', 'status': 'PASS' if share >= 0.20 else 'FAIL', 'value': f'{share:.0%}', 'note': '산업현황 분량 >= 20% (IR협의회 24%)'})
    r = outside_ratio(s04, name); out.append({'id': 'G2', 'status': 'PASS' if r >= 0.9 else 'FAIL', 'value': f'{r:.0%}', 'note': '산업현황 회사 밖 문단 >= 90% (IR협의회 96%)'})
    kinds = set(m.group(0).lower() for m in SRC.finditer(s04)); out.append({'id': 'G3', 'status': 'PASS' if len(kinds) >= 3 else 'FAIL', 'value': ','.join(sorted(kinds)) or '-', 'note': '협회·정부·산업리서치·고객사 공개자료 3종+'})
    m = MARGIN.findall(s01); ok4 = len(m) >= 3 and bool(NUM.search(m[0])) and bool(NAME.search(m[1])) and bool(TIME.search(m[2]))
    out.append({'id': 'G4', 'status': 'PASS' if ok4 else 'FAIL', 'value': f'{len(m)}개', 'note': '요약 한 줄 3개: (1)실적 수치 (2)회사 밖 실명 (3)시점'})
    ok5 = bool(re.search(r'밴드|Peer|비교기업', s07)) and not VAL.search(s01 + s02)
    out.append({'id': 'G5', 'status': 'PASS' if ok5 else 'FAIL', 'value': 'ok' if ok5 else 'SOTP/시나리오가 s01·s02 에 있음', 'note': '밸류는 밴드+Peer 본문, 시나리오는 판단 블록'})
    n6 = len(NEWS.findall(s04)); out.append({'id': 'G6', 'status': 'PASS' if n6 <= 2 else 'FAIL', 'value': str(n6), 'note': '산업현황의 뉴스 인용 <= 2 (IR협의회 뉴스 2%)'})
    return out


def main(argv=None):
    a = argv or sys.argv[1:]; stock = a[0]
    p = a[a.index('--analysis') + 1] if '--analysis' in a else f'scripts/analysis_{stock}_ta.json'
    res = check(json.load(open(p, encoding='utf-8')))
    for r in res:
        print(f"  [{'v' if r['status'] == 'PASS' else 'x'} {r['id']}] {r['status']:4s} {r['value']:20s} {r['note']}")
    fails = sum(1 for r in res if r['status'] == 'FAIL'); print(f'[industry_gate] FAIL {fails}건'); return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: 테스트 통과** -- 8개 통과
- [ ] **Step 5: 기존 두 리포트에 돌려 기준선 기록** -- `python scripts/ta_industry_gate.py 에프에스티` 와 `--analysis scripts/analysis_에프에스티_ta_agent.json`. 예상: G2·G3·G4 FAIL(현재 s04 가 뉴스·동사 중심). 결과를 `docs/research-ta-ablation.md` 에 한 줄 기록. **소급 수정하지 않는다.**
- [ ] **Step 6: Commit (사용자 승인 후)**

---

### Task 5: 커맨드·brief 형식 반영

**Files:**
- Modify: `.claude/commands/research-ta.md` (STEP 1 수집 목록, STEP 2 industry 분석가 입력, STEP 6 작성 형식, STEP 7 게이트)
- Modify: `docs/research-ta/brief_format.md` (industry brief 의 필수 출처 열)
- Modify: `data/에프에스티/ta/story_spine.md` 는 종목별이라 손대지 않고, 공용 규칙은 커맨드에만

**Interfaces:**
- Consumes: Task 1~4 의 CLI 이름과 산출 경로
- Produces: 문서만

- [ ] **Step 1: STEP 1 에 세 줄 추가** (기존 코드 블록 `python scripts/ta_plan_agents.py {종목명}` 바로 위)

```bash
python scripts/ta_trade_stats.py {종목명}          # ta/trade_query.json (HS·국가) 를 먼저 쓴다 -- 사업보고서 II장 제품·수출 지역
python scripts/ta_customer_docs.py {종목명}        # ta/customers.json (고객사·장비사·경쟁사, US=ticker / KR=이름, keywords)
python scripts/ta_company_voice.py {종목명} --irtv # 기업설명회 첨부 + 발언 기사 + IRTV 자막
```
그 아래 한 줄: `IR협의회 재료 비중(DART 26 / 자체 추정 26 / 회사 설명 18 / 협회·정부 12 / 고객사·경쟁사 8 / 뉴스 2 %) -- 뉴스는 재료가 아니라 사건 표기다. 근거 docs/research-ta/kirs-construction.md.`

- [ ] **Step 2: STEP 2 표의 industry 행** 을 `ta-industry-analyst` 입력에 `ta/trade_stats.json, ta/customer_docs/*.md` 를 명시하도록 고치고, sellside 행에 `ta/company_voice.md` 를 추가.

- [ ] **Step 3: STEP 6 작성 규칙 추가** (절대 규칙 8 아래 10·11 로)

```markdown
10. **요약은 ■ 3개 고정** (IR협의회 22편 전부): ① 회사가 무엇을 하고 최근 실적 사실(반기·분기 수치) ② 성장 동인 하나를 회사 밖 실명·수치로 ③ 앞으로의 일정·판단·밸류 위치 한 줄. `> **한 줄:**` 3개가 이 순서다(G4).
11. **산업현황은 회사 밖 재료로만 쓰고 마지막 한 문단에서 동사로 착지한다.** 분량 20%+, 회사 밖 문단 90%+, 출처 3종+(관세청·협회·SEMI·고객사 10-K·기업설명회), 뉴스 인용 2회 이하(G1~G3, G6). 재료는 ta/trade_stats.json, ta/customer_docs/, ta/company_voice.md.
12. **밸류는 밴드+Peer 로 "지금 위치"까지만 본문(s07)에, 등급·목표가·시나리오는 s07 끝 `#### 판단` 블록 하나에.** s01·s02 에는 SOTP·시나리오·DCF 단어를 쓰지 않는다(G5). IR협의회는 등급이 없지만 이 프로젝트는 실제 투자용이라 판단 블록을 둔다(사용자 결정 2026-09-17).
```

- [ ] **Step 4: STEP 7 게이트 목록에** `python scripts/ta_industry_gate.py {종목명}   # G1~G6 (0 FAIL)` 추가. 절대 규칙 8 의 s01·s02 밸류 용어 카운트 스크립트는 G5 로 대체됐다고 표시(둘 다 돌려도 됨).

- [ ] **Step 5: brief_format.md** 의 industry 절에 "필수 열: 출처 종류(협회·정부/산업리서치/고객사·경쟁사 공개자료/회사 설명) -- 뉴스는 종류로 인정하지 않는다" 한 줄 추가.

- [ ] **Step 6: 문법 확인** -- `python -c "import re;t=open('.claude/commands/research-ta.md',encoding='utf-8').read();print(len(t), t.count('ta_industry_gate'))"` -> 카운트 1 이상.
- [ ] **Step 7: Commit (사용자 승인 후)**

---

### Task 6: CJ프레시웨이로 검증 (실행 태스크)

**Files:** 산출만 (`data/CJ프레시웨이/ta/`, `scripts/analysis_CJ프레시웨이_ta.json`, `output/CJ프레시웨이_ta/`)

- [ ] **Step 1:** `/research-ta CJ프레시웨이` 를 STEP 0 부터. STEP 1 에서 `trade_query.json`(식자재 유통이라 HS 대신 `farm` 통계가 맞으면 관세청은 건너뛰고 manifest 에 사유), `customers.json`(단체급식 경쟁: 삼성웰스토리·아워홈·현대그린푸드 KR), `company_voice --irtv`.
- [ ] **Step 2:** 작성 후 `ta_industry_gate` 0 FAIL 을 다른 게이트와 함께 통과.
- [ ] **Step 3:** 블라인드 판정 -- IR협의회 CJ프레시웨이(2024-12-16, `data/_ref/kirs/_txt/CJ프레시웨이_79337.txt`) 대 -ta, cutoff 2024-12-16, 위치 교차 2회. 결과를 `docs/research-ta-ablation.md` 2절에.
- [ ] **Step 4:** 어느 축에서 졌는지를 다음 수정 입력으로.

---

## Self-Review
- Spec 7절 항목 대응: 수집(Task 1·2·3) / 산업현황 게이트(Task 4 G1~G3·G6) / 투자포인트 회사 설명 출처(Task 3 + Task 5 STEP 2) / 실적 추정 표(기존 장부 -- 별도 태스크 없음, 작성 규칙에 이미 있음) / 밸류 분리(Task 4 G5 + Task 5 규칙 12) / 뉴스 자리(Task 4 G6 + Task 5) / 분량(게이트로 두지 않음 -- IR협의회와 같은 급이라 현행 유지) / 요약 ■3(Task 4 G4 + Task 5 규칙 10).
- 시그니처 일관성: `parse_items`, `ttm_yoy`, `pick_paragraphs`, `is_boilerplate`, `is_company_statement`, `extract_statements`, `check`, `outside_ratio` -- 테스트와 구현이 같은 이름.
- 미확정 의존: `sec_edgar.get_filing_text` 존재 여부(Task 2 Step 3 에 대안 명시), `news.json` 내부 구조(Task 3 Step 3 에 확인 명령 명시).
