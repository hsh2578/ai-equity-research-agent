# -*- coding: utf-8 -*-
"""회사가 직접 말한 것 -> data/{종목}/ta/company_voice.md

IR협의회 투자포인트 재료의 26%가 공시에 없는 '회사 설명'(램리서치 품목 승인 수, 초도 PO, 인증기간 단축)이다
(docs/research-ta/kirs-construction.md 5절). 우리는 회사 미팅이 없으므로
(1) DART 기업설명회·기업가치제고 첨부 (2) 인터뷰·발언 기사(ta/news_relevant.json, ta_news_body 로 전문 확보 후) (3) IRTV 자막(yt-dlp) 으로 대체한다.

usage: python scripts/ta_company_voice.py {종목명} [--irtv]
"""
import glob
import io
import os
import re
import subprocess
import sys
from datetime import date, timedelta

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, r'C:/Users/hsh/Desktop')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ta_common import ta_dir, manifest_update, read_json, write_json, is_reaction_title  # noqa: E402

TITLE = re.compile(r'인터뷰|대표|CEO|회장|간담회|기업설명회|IR|밝혔|계획|전망')
SAY = re.compile(r'(대표|회장|사장|상무|이사|관계자|회사 측|회사측|동사)[^.。]{0,80}(밝혔|말했|설명했|강조했|언급했|전했|계획이라고|예정이라고)')
BROKER = re.compile(r'증권|목표주가|투자의견|리서치센터')
POLITICS = re.compile(r'의원|원내대표|장관|대통령|국회|정부는')  # 시황 모음 기사에 섞인 정치인 발언 제외


def is_company_statement(title, body):
    if is_reaction_title(title) or BROKER.search(title):
        return False
    return bool(TITLE.search(title) and not BROKER.search(body or '')) or bool(SAY.search(body or ''))


def extract_statements(body, max_n=8):
    sents = re.split(r'(?<=[.。])\s+', body or '')
    return [s.strip() for s in sents if SAY.search(s) and not POLITICS.search(s)][:max_n]


def news_statements(d):
    n = read_json(os.path.join(d, 'news_relevant.json')) or {}
    items = []
    for a in n.get('items') or []:
        t, b = a.get('title', ''), a.get('body_full') or a.get('body', '')  # ta_news_body 가 채운 전문 우선
        if is_company_statement(t, b):
            items.append({'date': (a.get('datetime') or '')[:10], 'title': t, 'url': a.get('url', ''),
                          'nid': a.get('nid'), 'statements': extract_statements(b) or [t]})
    return sorted(items, key=lambda x: x['date'], reverse=True)[:30]


def ir_filings(stock, d):
    from dart_api import get_corp_code, download_report_document, html_to_text
    from collect_dart_filings import fetch_list
    key = os.environ.get('DART_API_KEY')
    cc = get_corp_code(stock)
    corp = cc[0] if isinstance(cc, (list, tuple)) else cc  # (고유번호, 종목코드) 튜플
    end = date.today()
    bgn = end - timedelta(days=730)
    out = []
    for it in fetch_list(corp, bgn.strftime('%Y%m%d'), end.strftime('%Y%m%d'), key):
        nm = it.get('report_nm', '')
        if '기업설명회' not in nm and '기업가치제고' not in nm:
            continue
        for _fn, html in (download_report_document(it['rcept_no']) or {}).items():
            txt = html_to_text(html)
            p = os.path.join(d, f"_ir_{it['rcept_dt']}_{it['rcept_no']}.txt")
            with open(p, 'w', encoding='utf-8') as f:
                f.write(txt)
            out.append({'date': it['rcept_dt'], 'name': nm, 'file': os.path.basename(p), 'chars': len(txt)})
    return out


def irtv(stock, d):
    """yt-dlp 로 IRTV 검색 상위 3건의 자동자막(ko). 실패는 이유를 남긴다."""
    out_t = os.path.join(d, '_irtv_%(title)s.%(ext)s')
    r = subprocess.run(['yt-dlp', f'ytsearch3:IRTV {stock}', '--skip-download', '--write-auto-sub',
                        '--sub-lang', 'ko', '--sub-format', 'vtt', '-o', out_t],
                       capture_output=True, text=True, timeout=240)
    files = []
    for f in glob.glob(os.path.join(d, '_irtv_*.vtt')):  # 검색 노이즈: 제목에 종목명이 없으면 버린다
        if stock in os.path.basename(f):
            files.append(os.path.basename(f))
        else:
            os.remove(f)
    files.sort()
    return {'files': files, 'rc': r.returncode, 'err': (r.stderr or '')[-300:] if r.returncode else ''}


def main(argv=None):
    a = argv or sys.argv[1:]
    stock = a[0]
    use_irtv = '--irtv' in a
    from env_loader import load_env
    load_env()
    d = ta_dir(stock)
    res = {'asof': date.today().isoformat(), 'news': news_statements(d), 'ir_filings': [], 'irtv': None, 'failed': []}
    try:
        res['ir_filings'] = ir_filings(stock, d)
    except Exception as e:  # 실패 이유를 남긴다
        res['failed'].append({'step': 'ir_filings', 'reason': repr(e)[:200]})
    if use_irtv:
        try:
            res['irtv'] = irtv(stock, d)
        except Exception as e:
            res['failed'].append({'step': 'irtv', 'reason': repr(e)[:200]})
    km = read_json(os.path.join(d, 'ir_materials', 'index.json')) or {}
    res['kind_ir'] = [i for i in km.get('items', []) if i.get('status') == 'ok']
    md = [f"# {stock} -- 회사가 직접 말한 것 ({res['asof']})\n", '## IR 발표자료 (KIND IR자료실 ta_kind_ir + 회사 홈페이지 ta_company_ir)\n']
    # source=='site' 는 txt 가 ta/ 바로 아래(ir_site/...); 이미지 슬라이드면 png_dir 을 Read 로 본다
    md += [f"- {i['date']} {i['file']} -> ta/{i['txt'] if i.get('source') == 'site' else 'ir_materials/' + i['txt']} ({i['pages']}p, {i['chars']:,}자)"
           + (f" -- 이미지 슬라이드, PNG: ta/{i['png_dir']}/pNN.png" if i.get('png_dir') else '')
           for i in res['kind_ir']] or ['- 없음(ta_kind_ir·ta_company_ir 미실행 또는 자료 없음)']
    md += ['\n## IR 개최 공시(DART 첨부 -- 안내문)\n']
    md += [f"- {f['date']} {f['name']} -> ta/{f['file']} ({f['chars']:,}자)" for f in res['ir_filings']] or ['- 없음(2년 내 기업설명회 공시 없음)']
    md += ['\n## 인터뷰·발언 기사 (news_relevant.json 에서 판별)\n']
    for it in res['news']:
        md.append(f"### {it['date']} {it['title']} [{it['nid']}]\n" + '\n'.join(f'> {s}' for s in it['statements']) + f"\n{it['url']}\n")
    if res['irtv'] is not None:
        md += ['\n## IRTV 자막\n'] + [f'- ta/{f}' for f in res['irtv']['files']] + ([f"- 실패: {res['irtv']['err']}"] if res['irtv']['rc'] else [])
    with open(os.path.join(d, 'company_voice.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(md))
    write_json(os.path.join(d, 'company_voice.json'), res)
    n = len(res['news']) + len(res['ir_filings']) + len(res['kind_ir'])
    manifest_update(stock, 'company_voice', 'ok' if n else 'failed', news=len(res['news']), ir=len(res['ir_filings']),
                    irtv=len(res['irtv']['files']) if res['irtv'] else None, failed=len(res['failed']))
    print(f"[{'OK' if n else 'FAIL'}] company_voice: 발언 기사 {len(res['news'])}, IR 첨부 {len(res['ir_filings'])}, "
          f"IRTV {len(res['irtv']['files']) if res['irtv'] else '-'}, 실패 {len(res['failed'])} -> ta/company_voice.md")
    return 0 if n else 1


if __name__ == '__main__':
    sys.exit(main())
