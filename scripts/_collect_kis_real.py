"""KIS 실전 엔드포인트로 표준 수집 파이프라인 실행.

모의 서버(openapivts:29443)가 HTTP 500 을 낼 때 쓴다 (실측 2026-09-08:
source_health 에서 kis 3회 시도 모두 500). 실전 자격증명은 통합 .env 의
KIS_REAL_APP_KEY / KIS_REAL_APP_SECRET / KIS_BASE_URL_ALT2 에 있다.

환경변수만 바꿔 자식 프로세스로 표준 스크립트를 그대로 호출한다.
(shell 환경변수가 .env 보다 우선하므로 자식이 실전값을 쓴다.)
**키 값은 절대 출력하지 않는다.**

사용: python scripts/_collect_kis_real.py {종목명} {종목코드} {업종키}
"""
import io
import os
import subprocess
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, r"C:/Users/hsh/Desktop")
from env_loader import load_env   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def use_real_kis():
    """실전 자격증명을 표준 키 이름으로 승격. 성공 여부만 보고한다."""
    load_env()
    swapped = []
    for real, std in (('KIS_REAL_APP_KEY', 'KIS_APP_KEY'),
                      ('KIS_REAL_APP_SECRET', 'KIS_APP_SECRET'),
                      ('KIS_BASE_URL_ALT2', 'KIS_BASE_URL')):
        v = os.environ.get(real)
        if v:
            os.environ[std] = v
            swapped.append(std)
    base = os.environ.get('KIS_BASE_URL', '')
    if ':9443' not in base:
        print(f'[WARN] 실전 엔드포인트가 아니다: {base}')
    print(f'[OK] KIS 실전 전환 ({len(swapped)}개 키) BASE={base}')
    return bool(swapped)


def run(label, args, timeout=420):
    print(f'\n--- {label} ---')
    try:
        r = subprocess.run([sys.executable] + args, cwd=ROOT, timeout=timeout,
                           capture_output=True, text=True, encoding='utf-8',
                           errors='replace')
    except subprocess.TimeoutExpired:
        print(f'[FAIL] {label}: 타임아웃 {timeout}s')
        return False
    out = (r.stdout or '') + (r.stderr or '')
    tail = '\n'.join(out.strip().splitlines()[-6:])
    print(tail if tail else '(출력 없음)')
    if r.returncode != 0:
        print(f'[FAIL] {label}: exit {r.returncode}')
    return r.returncode == 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    name, code = sys.argv[1], sys.argv[2]
    sector = sys.argv[3] if len(sys.argv) > 3 else None

    use_real_kis()
    os.makedirs(os.path.join(ROOT, 'data', name), exist_ok=True)

    steps = [
        ('financial_summary', ['scripts/financial_summary.py', name, code]),
        ('fdr_band', ['scripts/fdr_band.py', name, code]),
        ('volatility_beta', ['scripts/volatility_beta.py', name, code]),
        # dart_quarterly 의 2번째 위치인자는 **연도**다 (종목코드를 넘기면
        # bsns_year=012450 이 되어 전 분기 '항목 0개' 로 조용히 실패한다)
        ('dart_quarterly', ['scripts/dart_quarterly.py', name, '2025', '2026']),
    ]
    if sector:
        steps.append(('peer_snapshot', ['scripts/peer_snapshot.py', name, sector]))

    ok = 0
    for label, args in steps:
        if run(label, args):
            ok += 1
    run('build_snapshot', ['scripts/build_snapshot.py', name])
    print(f'\n[완료] {ok}/{len(steps)} 성공')
    return 0


if __name__ == '__main__':
    sys.exit(main())
