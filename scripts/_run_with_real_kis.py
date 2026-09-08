# -*- coding: utf-8 -*-
"""KIS 실전 엔드포인트로 다른 스크립트를 실행하는 래퍼.

모의 서버(openapivts:29443)가 간헐적으로 HTTP 500 을 낸다(CLAUDE.md 기록).
실전 자격증명은 마스터 .env 의 KIS_REAL_APP_KEY / KIS_REAL_APP_SECRET,
엔드포인트는 KIS_BASE_URL_ALT2 에 있다.

사용: python scripts/_run_with_real_kis.py <스크립트> [인자...]
값은 절대 출력하지 않는다 -- 어떤 키를 썼는지만 알린다.
"""
import io
import os
import subprocess
import sys

if getattr(sys.stdout, 'encoding', '') != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, r"C:/Users/hsh/Desktop")
try:
    from env_loader import load_env
    load_env()
except Exception as e:                                   # noqa: BLE001
    print(f'[WARN] env_loader 실패: {type(e).__name__}')

env = os.environ.copy()
swapped = []
for real, target in (('KIS_REAL_APP_KEY', 'KIS_APP_KEY'),
                     ('KIS_REAL_APP_SECRET', 'KIS_APP_SECRET'),
                     ('KIS_BASE_URL_ALT2', 'KIS_BASE_URL')):
    v = env.get(real)
    if v:
        env[target] = v
        swapped.append(f'{real} -> {target}')

if not swapped:
    print('[ERR] 실전 자격증명을 찾지 못했다. 모의 그대로 실행한다.')
else:
    for line in swapped:
        print(f'[env] {line}')
print(f'[env] KIS_BASE_URL 호스트 = {env.get("KIS_BASE_URL", "").split("//")[-1]}')

# 토큰 캐시가 모의 서버 것으로 남아 있으면 실전에서 거부된다
for cache in ('scripts/.kis_token.json', '.kis_token.json',
              'scripts/kis_token.json'):
    if os.path.exists(cache):
        os.remove(cache)
        print(f'[env] 토큰 캐시 제거: {cache}')

if len(sys.argv) < 2:
    print(__doc__)
    raise SystemExit(2)

sys.exit(subprocess.call([sys.executable] + sys.argv[1:], env=env))
