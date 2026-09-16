"""ta_render.py 테스트 (Task 12).

generate_all.py(수정 금지, 실제로 호출하지 않는다)의 출력 폴더가
output/{종목}/ 로 고정이라 /research-ta 가 기존 /research PDF 를 덮어쓰면
안 된다. 이 래퍼가 백업 -> 실행(가짜 러너) -> diff 복사 -> 복원을 제대로
하는지, 실제 output/ 폴더는 건드리지 않고 tempdir 로만 검증한다.

실행: python tests/test_ta_render.py
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import ta_common as tc                                   # noqa: E402
import ta_render as tr                                    # noqa: E402

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


def _write_analysis(td, stock_name):
    path = os.path.join(td, 'scripts', f'analysis_{stock_name}_ta.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'meta': {'stock_name': stock_name}}, f, ensure_ascii=False)
    return path


def _make_pdf(path, page_texts):
    import fitz
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        # 기본 폰트는 한글 글리프가 없어 get_text() 가 깨진다 -- 내장 CJK 폰트 사용
        page.insert_text((72, 72), text, fontsize=11, fontname='korea-s')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    doc.save(path)
    doc.close()


# ==================== 시나리오 A: 기존 output 폴더 있음 ====================

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '테스트종목'
        analysis_path = _write_analysis(td, stock)

        out_dir = os.path.join(td, 'output', stock)
        os.makedirs(out_dir, exist_ok=True)
        pdf_rel = f'report_{stock}_상세.pdf'
        with open(os.path.join(out_dir, pdf_rel), 'wb') as f:
            f.write(b'ORIGINAL-PDF-BYTES')
        with open(os.path.join(out_dir, 'untouched.txt'), 'w', encoding='utf-8') as f:
            f.write('keep me')

        def fake_runner(argv, cwd):
            # generate_all.py 가 하듯 기존 PDF 를 덮어쓴다
            with open(os.path.join(out_dir, pdf_rel), 'wb') as f:
                f.write(b'NEW-PDF-BYTES-FROM-RUN')
            return subprocess.CompletedProcess(argv, 0, stdout='[OK] 완료 33페이지', stderr='[WARN] 한글 경고')

        result = tr.render(stock, analysis_path=analysis_path, runner=fake_runner)

        eq(result['returncode'], 0, 'A: returncode 0')
        eq(result['restored'], True, 'A: restored True')
        eq('copied' in result and pdf_rel in result['copied'], True, 'A: 바뀐 PDF 가 copied 목록에 있음')
        eq(result['stdout_tail'], '[OK] 완료 33페이지', 'A: stdout_tail 에 한글 그대로')
        eq(result['stderr_tail'], '[WARN] 한글 경고', 'A: stderr_tail 도 결과에 남는다')

        with open(os.path.join(out_dir, pdf_rel), 'rb') as f:
            restored_bytes = f.read()
        eq(restored_bytes, b'ORIGINAL-PDF-BYTES', 'A: output/{종목}/ PDF 원본 복원')

        with open(os.path.join(out_dir, 'untouched.txt'), encoding='utf-8') as f:
            eq(f.read(), 'keep me', 'A: 안 바뀐 파일도 그대로')

        ta_out = os.path.join(td, 'output', f'{stock}_ta')
        with open(os.path.join(ta_out, pdf_rel), 'rb') as f:
            eq(f.read(), b'NEW-PDF-BYTES-FROM-RUN', 'A: _ta 폴더엔 새 PDF')

        render_result_path = os.path.join(ta_out, 'render_result.json')
        eq(os.path.exists(render_result_path), True, 'A: render_result.json 저장됨')
    finally:
        tc.PROJECT_ROOT = orig_root


# ==================== 시나리오 B: 기존 output 폴더 없음 ====================

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '새종목'
        analysis_path = _write_analysis(td, stock)
        out_dir = os.path.join(td, 'output', stock)
        pdf_rel = f'report_{stock}_상세.pdf'

        def fake_runner(argv, cwd):
            os.makedirs(out_dir, exist_ok=True)
            with open(os.path.join(out_dir, pdf_rel), 'wb') as f:
                f.write(b'FRESH-PDF')
            return subprocess.CompletedProcess(argv, 0, stdout='ok', stderr='')

        result = tr.render(stock, analysis_path=analysis_path, runner=fake_runner)

        eq(os.path.isdir(out_dir), False, 'B: 원래 없던 output/{종목} 은 끝나면 다시 없음')
        ta_out = os.path.join(td, 'output', f'{stock}_ta')
        eq(os.path.exists(os.path.join(ta_out, pdf_rel)), True, 'B: _ta 폴더엔 생성됨')
        eq(result['restored'], True, 'B: restored True')
    finally:
        tc.PROJECT_ROOT = orig_root


# ==================== 시나리오 C: 러너가 예외를 던짐 ====================

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = '예외종목'
        analysis_path = _write_analysis(td, stock)
        out_dir = os.path.join(td, 'output', stock)
        os.makedirs(out_dir, exist_ok=True)
        pdf_rel = f'report_{stock}_상세.pdf'
        with open(os.path.join(out_dir, pdf_rel), 'wb') as f:
            f.write(b'ORIGINAL')

        def boom_runner(argv, cwd):
            # 부분 실행 후 죽는 상황을 흉내: 파일을 건드리고 나서 예외
            with open(os.path.join(out_dir, pdf_rel), 'wb') as f:
                f.write(b'HALF-WRITTEN')
            raise RuntimeError('boom')

        result = tr.render(stock, analysis_path=analysis_path, runner=boom_runner)

        eq(result['returncode'], -1, 'C: 예외 시 returncode -1')
        eq('runner_exception' in result, True, 'C: runner_exception 기록')
        eq(result['restored'], True, 'C: 예외가 나도 restored True')
        with open(os.path.join(out_dir, pdf_rel), 'rb') as f:
            eq(f.read(), b'ORIGINAL', 'C: 예외가 나도 output/{종목}/ 원본 복원')
    finally:
        tc.PROJECT_ROOT = orig_root


# ==================== 시나리오 D: stock_name 불일치 ====================

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        analysis_path = _write_analysis(td, 'A종목')
        raised = False
        try:
            tr.render('B종목', analysis_path=analysis_path, runner=lambda argv, cwd: None)
        except ValueError:
            raised = True
        eq(raised, True, 'D: meta.stock_name 불일치 시 ValueError')
    finally:
        tc.PROJECT_ROOT = orig_root


# ==================== 시나리오 E: PNG 생성 ====================

with tempfile.TemporaryDirectory() as td:
    orig_root = tc.PROJECT_ROOT
    tc.PROJECT_ROOT = td
    try:
        stock = 'PNG종목'
        analysis_path = _write_analysis(td, stock)
        out_dir = os.path.join(td, 'output', stock)
        pdf_rel = f'report_{stock}_상세.pdf'

        page1_text = '표지'  # 30자 미만 -> 빈 페이지
        page2_text = ('기술적 분석 섹션입니다. ' * 3)  # 30자 이상 + 마커 포함

        def fake_runner(argv, cwd):
            _make_pdf(os.path.join(out_dir, pdf_rel), [page1_text, page2_text])
            return subprocess.CompletedProcess(argv, 0, stdout='ok', stderr='')

        result = tr.render(stock, analysis_path=analysis_path, runner=fake_runner)

        eq(result['pages'], 2, 'E: 총 2페이지')
        eq(result['blank_pages'], [1], 'E: 1페이지가 빈 페이지(텍스트 30자 미만)')
        eq(len(result['png']), 2, 'E: png 2장 생성 (1, auto=2)')

        ta_out = os.path.join(td, 'output', f'{stock}_ta')
        eq(os.path.exists(os.path.join(ta_out, 'png', 'p1.png')), True, 'E: p1.png 존재')
        eq(os.path.exists(os.path.join(ta_out, 'png', 'p2.png')), True, 'E: p2.png 존재 (기술적 분석 페이지)')
    finally:
        tc.PROJECT_ROOT = orig_root


# ==================== 시나리오 F: 기본 러너 -- UTF-8 한글 stdout/stderr ====================
# 실측 결함: generate_all.py 는 UTF-8 로 한글을 찍는데 Windows 콘솔 기본 인코딩은
# cp949 라, subprocess.run(text=True) 가 플랫폼 기본 인코딩으로 디코딩하면 내부
# 리더 스레드가 UnicodeDecodeError 로 죽어 stdout_tail 이 통째로 비고 트레이스백이
# 찍혔다(에프에스티 실행 확인). generate_all.py 를 실제로 돌리지 않고, 같은
# 조건(자식 프로세스가 UTF-8 바이트로 한글을 찍는다)만 재현하는 최소 서브프로세스로
# _default_runner 가 안 죽고 정확히 디코딩하는지 검증한다.
_child_code = (
    "import sys\n"
    "sys.stdout.buffer.write('완료 [OK] 33페이지\\n'.encode('utf-8'))\n"
    "sys.stderr.buffer.write('경고: 인코딩 점검\\n'.encode('utf-8'))\n"
)
cp = tr._default_runner([sys.executable, '-c', _child_code], os.getcwd())
eq(cp.returncode, 0, 'F: 기본 러너가 UTF-8 한글 출력에도 예외 없이 종료')
eq('완료' in (cp.stdout or ''), True, 'F: stdout 한글이 깨지지 않고 디코딩됨')
eq('경고' in (cp.stderr or ''), True, 'F: stderr 한글도 정상 디코딩됨')


print('=' * 66)
if _failed:
    for label, want, got in _failed:
        print(f'  [FAIL] {label}\n      기대: {want!r}\n      실제: {got!r}')
print(f'  ta_render 테스트: {_passed}개 통과 / {len(_failed)}개 실패')
print('=' * 66)
sys.exit(1 if _failed else 0)
