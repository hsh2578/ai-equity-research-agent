# -*- coding: utf-8 -*-
"""ta_render.py -- generate_all.py 안전 래퍼 (Task 12, /research-ta).

`generate_all.py`(공용, 수정 금지)는 출력 폴더가 `output/{meta.stock_name}/` 로
고정이다. `/research-ta` 리포트를 만들 때 기존 `/research` PDF 를 덮어쓰지
않도록 감싼다:

  1. `output/{종목}/` 가 있으면 임시 폴더에 복사로 백업 (이동 금지).
  2. `generate_all.py` 를 서브프로세스로 실행 (러너 주입 가능).
  3. 새로 생기거나 바뀐 파일만 `output/{종목}_ta/` 로 복사.
  4. `finally` 에서 `output/{종목}/` 를 백업 상태로 복원 (원래 없었으면 삭제).
  5. `_ta` 폴더의 PDF 에서 1페이지 + '기술적 분석' 첫 등장 페이지를 PNG 로 저장.

사용법: python scripts/ta_render.py {종목명} [--analysis scripts/analysis_{종목명}_ta.json] [--png-pages 1,auto]
"""
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

if (getattr(sys.stdout, 'encoding', '') or '').lower().replace('-', '') != 'utf8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ta_common as tc  # noqa: E402

_STDOUT_TAIL_CHARS = 2000
_TECH_ANALYSIS_MARKER = '기술적 분석'
_BLANK_PAGE_CHARS = 30
_PNG_DPI = 110


# ==================== 러너 ====================

def _default_runner(argv, cwd):
    # generate_all.py 는 UTF-8(한글 콘솔 출력)로 찍는데 Windows 기본 콘솔 인코딩은
    # cp949 라 text=True(플랫폼 기본 인코딩) 로 읽으면 subprocess 내부 리더 스레드가
    # UnicodeDecodeError 로 죽어 stdout_tail 이 통째로 빈다(실측: 에프에스티 회차).
    # encoding='utf-8' + errors='replace' 로 강제하고, 자식 프로세스도 같은
    # 인코딩으로 쓰도록 PYTHONIOENCODING 을 넘긴다.
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    return subprocess.run(argv, cwd=cwd, capture_output=True,
                           encoding='utf-8', errors='replace', env=env)


# ==================== 스냅샷(백업 대비 신규/변경 판별) ====================

def _file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _snapshot(root):
    """root 아래 모든 파일의 {상대경로: sha256} 딕셔너리. root 가 없으면 {}."""
    snap = {}
    if not os.path.isdir(root):
        return snap
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            snap[rel] = _file_hash(full)
    return snap


# ==================== PNG ====================

def _resolve_png_pages(doc, spec):
    """'1,auto' 같은 스펙을 1-based 페이지 번호 리스트로. 'auto' 는 텍스트에
    '기술적 분석' 이 처음 나오는 페이지. 정수 토큰은 그 페이지. 순서 보존,
    중복 제거, 범위 밖/못 찾은 auto 는 조용히 건너뛴다."""
    tokens = [t.strip() for t in (spec or '').split(',') if t.strip()]
    pages = []
    for tok in tokens:
        if tok == 'auto':
            for i in range(len(doc)):
                if _TECH_ANALYSIS_MARKER in (doc[i].get_text() or ''):
                    pages.append(i + 1)
                    break
        else:
            try:
                n = int(tok)
            except ValueError:
                continue
            if 1 <= n <= len(doc):
                pages.append(n)
    seen = set()
    ordered = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def _render_png(pdf_path, ta_output_dir, png_pages_spec):
    """반환: (총페이지수, 빈페이지 목록(1-based), 저장한 png 경로 목록, 에러문자열 또는 None).
    PDF 가 없거나 깨졌으면(러너가 중간에 죽은 경우 등) 예외를 올리지 않고 에러를
    구조화해 돌려준다 -- render() 의 백업 복원은 이미 끝난 뒤이므로 여기서 죽으면
    render_result.json 자체가 안 쓰여 원인을 알 수 없게 된다."""
    if not os.path.exists(pdf_path):
        return 0, [], [], None
    import fitz  # 지연 import -- 이 함수를 안 쓰는 호출자는 fitz 없이도 동작
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        return 0, [], [], f'{type(e).__name__}: {e}'
    try:
        n_pages = len(doc)
        blank_pages = [i + 1 for i in range(n_pages)
                       if len((doc[i].get_text() or '').strip()) < _BLANK_PAGE_CHARS]
        page_numbers = _resolve_png_pages(doc, png_pages_spec)
        png_dir = os.path.join(ta_output_dir, 'png')
        os.makedirs(png_dir, exist_ok=True)
        mat = fitz.Matrix(_PNG_DPI / 72, _PNG_DPI / 72)
        png_list = []
        for p in page_numbers:
            pix = doc[p - 1].get_pixmap(matrix=mat)
            out_path = os.path.join(png_dir, f'p{p}.png')
            pix.save(out_path)
            png_list.append(out_path)
        return n_pages, blank_pages, png_list, None
    finally:
        doc.close()


# ==================== 핵심 ====================

def render(stock_name, analysis_path=None, runner=None, png_pages='1,auto'):
    """generate_all.py 를 안전하게 실행하고 결과를 output/{종목}_ta/ 에 남긴다.
    output/{종목}/ 은 실행 전 상태로 항상 복원된다 (finally). 반환값은
    render_result.json 과 동일한 dict.
    """
    runner = runner or _default_runner

    if analysis_path is None:
        analysis_path = os.path.join(tc.PROJECT_ROOT, 'scripts', f'analysis_{stock_name}_ta.json')

    analysis = tc.read_json(analysis_path, default=None)
    if analysis is None:
        raise FileNotFoundError(f'analysis json 없음: {analysis_path}')
    meta_name = (analysis.get('meta') or {}).get('stock_name')
    if meta_name != stock_name:
        raise ValueError(
            f"analysis json 의 meta.stock_name({meta_name!r}) 이 인자 종목명({stock_name!r}) 과 다름 "
            "-- generate_all.py 는 meta.stock_name 으로 데이터 경로를 찾는다")

    # generate_all.py 의 출력 폴더명은 meta.stock_name 에서 공백을 뗀 값이다.
    out_name = meta_name.replace(' ', '')
    output_dir = os.path.join(tc.PROJECT_ROOT, 'output', out_name)
    ta_output_dir = os.path.join(tc.PROJECT_ROOT, 'output', f'{out_name}_ta')

    existed_before = os.path.isdir(output_dir)
    backup_dir = tempfile.mkdtemp(prefix='ta_render_backup_')
    before_snapshot = {}
    if existed_before:
        shutil.copytree(output_dir, backup_dir, dirs_exist_ok=True)
        before_snapshot = _snapshot(backup_dir)

    returncode = -1
    stdout_tail = ''
    stderr_tail = ''
    runner_exception = None
    copied = []

    try:
        try:
            result = runner(
                [sys.executable, os.path.join('scripts', 'generate_all.py'), analysis_path],
                tc.PROJECT_ROOT)
            returncode = getattr(result, 'returncode', None)
            stdout_tail = (getattr(result, 'stdout', '') or '')[-_STDOUT_TAIL_CHARS:]
            stderr_tail = (getattr(result, 'stderr', '') or '')[-_STDOUT_TAIL_CHARS:]
        except Exception as e:
            runner_exception = f'{type(e).__name__}: {e}'
            stdout_tail = runner_exception

        after_snapshot = _snapshot(output_dir)
        if after_snapshot:
            os.makedirs(ta_output_dir, exist_ok=True)
        for rel, filehash in after_snapshot.items():
            if before_snapshot.get(rel) != filehash:
                src = os.path.join(output_dir, rel)
                dst = os.path.join(ta_output_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                copied.append(rel)
    finally:
        if os.path.isdir(output_dir):
            shutil.rmtree(output_dir)
        if existed_before:
            shutil.copytree(backup_dir, output_dir)
        if os.path.isdir(backup_dir):
            shutil.rmtree(backup_dir)

    pdf_path = os.path.join(ta_output_dir, f'report_{out_name}_상세.pdf')
    pages, blank_pages, png_list, png_error = _render_png(pdf_path, ta_output_dir, png_pages)

    render_result = {
        'returncode': returncode,
        'stdout_tail': stdout_tail,
        'stderr_tail': stderr_tail,
        'copied': sorted(copied),
        'restored': True,
        'pages': pages,
        'blank_pages': blank_pages,
        'png': png_list,
    }
    if runner_exception:
        render_result['runner_exception'] = runner_exception
    if png_error:
        render_result['png_error'] = png_error

    os.makedirs(ta_output_dir, exist_ok=True)
    tc.write_json(os.path.join(ta_output_dir, 'render_result.json'), render_result)

    status = 'ok' if returncode == 0 else 'failed'
    tc.manifest_update(stock_name, 'render', status, returncode=returncode, pages=pages)

    return render_result


# ==================== CLI ====================

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('stock')
    ap.add_argument('--analysis', default=None)
    ap.add_argument('--png-pages', default='1,auto')
    a = ap.parse_args(argv)

    try:
        result = render(a.stock, analysis_path=a.analysis, png_pages=a.png_pages)
    except (FileNotFoundError, ValueError) as e:
        print(f'[ta_render] 실패: {e}')
        return 1

    print(f"[ta_render] {a.stock} -- returncode={result['returncode']} "
          f"복사 {len(result['copied'])}개 페이지 {result['pages']} "
          f"빈페이지 {len(result['blank_pages'])}개 png {len(result['png'])}개")
    return 0 if result['returncode'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
