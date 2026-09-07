"""
fetch_broker_reports 스로틀/페이지 예산 테스트 (TDD -- 구현보다 먼저 작성됨)

코드리뷰 지적: 다운로드 단계는 polite_downloader(delay=0.6, workers=2) 로 조심하는데
정작 차단 위험이 큰 **목록 수집 단계**(fr.fetch_range)는 최대 400 페이지를 지연 없이
전 카테고리로 훑었다. 게다가 최종 선택은 8건 이하다.

여기서 고정하는 계약:
  1. 페이지 사이에 지연을 넣는다 (첫 페이지는 지연 없음).
  2. --months 에 비례해 페이지 예산을 정한다 (한경 실측: 20행/페이지, 약 37페이지/월).
  3. 필요한 매칭 건수를 채우면 조기 종료한다 (fetch_range 는 빈 파싱 결과에서 break).
  4. workers 는 docstring 대로 2 로 클램프한다 (기존 `> 3` 가드는 3 을 통과시켰다).

scripts/broker/ 는 이식본이라 수정하지 않는다. 전부 래퍼에서 해결한다.

실행: python tests/test_fetch_broker_reports.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))

import fetch_broker_reports as fb  # noqa: E402

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


class R:
    """Report 스텁 (dataclass 대신 필요한 필드만)."""

    def __init__(self, title='', category='기업', author='', publisher='', date='2026-09-01'):
        self.title = title
        self.category = category
        self.author = author
        self.publisher = publisher
        self.date = date
        self.report_idx = title


# --- 1. workers 클램프: docstring 은 "2 를 넘기지 말 것" ---
eq(fb.clamp_workers(2), (2, None), "2 는 그대로")
eq(fb.clamp_workers(1), (1, None), "1 은 그대로")
eq(fb.clamp_workers(3)[0], 2, "3 도 2 로 낮춘다 (기존 `> 3` 가드는 3 을 통과시켰다)")
truthy(fb.clamp_workers(3)[1], "낮췄으면 경고 문구를 돌려준다")
eq(fb.clamp_workers(8)[0], 2, "8 -> 2")

# --- 2. 페이지 예산: months 에 비례, 상한/하한 존재 ---
b3 = fb.page_budget(3)
b6 = fb.page_budget(6)
truthy(b3 < b6, "기간이 길면 예산도 늘어난다")
truthy(100 <= b3 <= 200, f"3개월 예산은 실측 커버리지(약 113p) 근처여야 한다: {b3}")
truthy(b6 <= 400, "상한 400 페이지를 넘지 않는다")
eq(fb.page_budget(60), 400, "아주 긴 기간은 상한에서 잘린다")
truthy(fb.page_budget(1) >= 20, "짧은 기간에도 최소 페이지는 확보")

# --- 3. keyword/카테고리 매칭 ---
r_hit = R(title='한국콜마(161890) 실적 리뷰', category='기업')
r_cat = R(title='한국콜마 산업 코멘트', category='산업')
r_daily = R(title='한국콜마 Daily 코멘트', category='기업')
eq(fb.matches(r_hit, '한국콜마', '기업'), True, "제목 키워드 + 카테고리 일치")
eq(fb.matches(r_cat, '한국콜마', '기업'), False, "카테고리 불일치는 제외")
eq(fb.matches(r_daily, '한국콜마', '기업'), False, "데일리성 리포트는 제외")
eq(fb.matches(R(title='기타 종목'), '한국콜마', '기업'), False, "키워드 불일치는 제외")

# --- 4. paged_fetcher: 페이지 사이 지연 + 예산 초과 시 조기 종료 ---
sleeps, urls = [], []


def fake_fetch(url):
    urls.append(url)
    return 'HTML'


f = fb.paged_fetcher(delay=0.7, max_pages=2, fetch=fake_fetch,
                     parse=lambda h: [R(title='x')], sleeper=sleeps.append)
eq(f('u1'), 'HTML', "1페이지 정상 반환")
eq(sleeps, [], "첫 페이지 앞에는 지연 없음")
eq(f('u2'), 'HTML', "2페이지 정상 반환")
eq(sleeps, [0.7], "두 번째 요청 앞에 지연 1회")
eq(f('u3'), '', "예산 초과 -> 빈 문자열 (fetch_range 가 break 한다)")
eq(len(urls), 2, "예산을 넘으면 실제 요청을 보내지 않는다")

# --- 5. paged_fetcher: 필요한 건수를 채우면 조기 종료 ---
sleeps2, urls2 = [], []
pages = [[R(title='한국콜마 A')], [R(title='한국콜마 B')], [R(title='한국콜마 C')]]
state = {'i': 0}


def fake_fetch2(url):
    urls2.append(url)
    return 'HTML'


def fake_parse(html):
    i = state['i']
    state['i'] += 1
    return pages[i] if i < len(pages) else []


f2 = fb.paged_fetcher(delay=0.1, max_pages=50, fetch=fake_fetch2, parse=fake_parse,
                      sleeper=sleeps2.append,
                      stop_when=lambda rows: len(rows) >= 2)
eq(f2('u1'), 'HTML', "1페이지")
eq(f2('u2'), 'HTML', "2페이지 (여기서 누적 2건 -> 목표 달성)")
eq(f2('u3'), '', "목표 달성 후에는 조기 종료")
eq(len(urls2), 2, "목표 달성 후 추가 요청 없음")

print(f"\n{'=' * 60}")
print(f"  fetch_broker_reports 테스트: {_passed}개 통과 / {len(_failed)}개 실패")
print(f"{'=' * 60}")
for f in _failed:
    print(f"  [FAIL] {f}")
sys.exit(1 if _failed else 0)
