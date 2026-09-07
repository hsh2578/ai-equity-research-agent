# broker/ -- 한경 컨센서스 리포트 수집기 (이식)

출처: 사용자의 별도 프로젝트 `주식 리포트 카카오톡` 의 `weekly-stock-report-skill/scripts/`.
2회 이상의 실전 주간 리포트 생성으로 검증된 코드이며, 그대로 이식했다.

이 프로젝트에서 쓰는 이유: `/wf-report` 는 "산업 3+ / 기업 3+ 애널리스트 리포트 정독"
을 의무로 규정하면서도 정작 수집기가 없어서, 매 종목마다 `_cw_fetch_reports.py`
`_cw_dl.py` `_oci_hist_analyst.py` 같은 일회용 스크립트를 새로 작성해 왔다.

## 실전에서 얻은 주의사항 (원 프로젝트 CLAUDE.md 에서 이관)

- **한경은 IP 단위로 rate limit 을 건다.** 동시성 8 + 별도 작업 3 으로 약 900 요청 후
  PDF 는 물론 목록 페이지까지 전부 403. Referer 를 붙여도 소용없다.
  **`--workers 2 --delay 0.6` 이하로 쓴다.** fetch_all 은 403/429/5xx 를
  30/90/240/600초 백오프로 재시도하고 이미 받은 `{idx}.txt` 는 건너뛴다.
- **목록 URL 에 `?skinType=...` 을 절대 붙이지 않는다.** 카테고리 열이 사라져
  파싱이 밀리고 제목이 category 로 들어간다 (데일리 필터가 무력화됨).
- **인코딩**: 한경 페이지는 UTF-8, 네이버 리서치는 EUC-KR. fetch_url 이 순차 시도한다.
- 페이지 수 필터는 다운로드 후에만 가능하다 (목록에 페이지 열이 없다).

## 사용

    python scripts/fetch_broker_reports.py 한국콜마 --category 기업 --months 6
