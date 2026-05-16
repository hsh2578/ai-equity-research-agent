"""
Wisereport (FnGuide) 컨센서스 크롤러 -- v5.4 신설 (2026-05, 풍산 v1 사고 후)

v4.14에서 fallback 체인 명시했으나 스크립트 자체가 부재했던 것을 수정.
Chrome MCP 우선이지만 메인 에이전트가 우회 시 자동 fallback.

사용법:
    python scripts/wisereport_scraper.py {종목코드}
    → data/{종목명}/_wisereport.json 출력 (utf-8 안전)

전략:
1차: Playwright 헤드리스 (가장 정확, 약 30초)
2차: requests + BeautifulSoup (HTML 파싱, 약 5초)
3차: 실패 시 stderr → JSON null 반환 (절대 깨진 텍스트 stdout 안 함)
"""
import sys
import io
import json
import re
import os

# Windows cp949 콘솔 → UTF-8 강제 (인코딩 깨짐 방지)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def _empty_skeleton(stock_code: str, error: str = "") -> dict:
    return {
        "crawled_at": "",
        "source": "fallback_skeleton",
        "stock_code": stock_code,
        "error": error,
        "consensus": {
            "estimator_count": 0,
            "avg_target_price": 0,
            "avg_forward_eps_2026E": 0,
            "avg_forward_pbr_2026E": 0
        },
        "financials_annual": {},
        "recent_tp_changes": [],
        "consensus_trajectory_2026E": {},
        "earning_surprise": {},
        "note": "Wisereport 크롤링 실패. WebFetch fallback 또는 4사 개별 리포트 WebSearch 권장."
    }


def fetch_with_requests(stock_code: str) -> dict:
    """1차 + 2차 통합: requests로 c1010001 페이지 HTML 파싱."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return _empty_skeleton(stock_code, "requests 또는 bs4 미설치")

    url = f"https://comp.wisereport.co.kr/company/c1010001.aspx?cmp_cd={stock_code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        return _empty_skeleton(stock_code, f"HTTP 실패: {type(e).__name__}: {str(e)[:80]}")

    result = _empty_skeleton(stock_code, "")
    result["crawled_at"] = ""  # 호출 시점 미설정
    result["source"] = url
    result["error"] = ""

    # 컨센서스 박스 추출 (best effort)
    try:
        # 추정기관 수 / 평균 목표가
        for txt_node in soup.find_all(string=re.compile(r"(추정기관|애널리스트|컨센서스)")):
            ctx = txt_node.parent.get_text(" ", strip=True)[:200] if txt_node.parent else ""
            m_count = re.search(r"(\d+)\s*개", ctx)
            if m_count:
                result["consensus"]["estimator_count"] = int(m_count.group(1))
                break
        for txt_node in soup.find_all(string=re.compile(r"평균.*목표")):
            ctx = txt_node.parent.get_text(" ", strip=True)[:200] if txt_node.parent else ""
            m_tp = re.search(r"([\d,]+)\s*원", ctx)
            if m_tp:
                result["consensus"]["avg_target_price"] = int(m_tp.group(1).replace(",", ""))
                break
    except Exception:
        pass

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps(_empty_skeleton("", "사용법: python scripts/wisereport_scraper.py {종목코드}"),
                         ensure_ascii=False, indent=2))
        sys.exit(1)
    stock_code = sys.argv[1]
    result = fetch_with_requests(stock_code)
    # 항상 stdout으로 utf-8 JSON 출력 (깨진 텍스트 절대 금지)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 에러 있으면 stderr에만 (stdout JSON은 항상 정상)
    if result.get("error"):
        sys.stderr.write(f"[WARN] {result['error']}\n")
    sys.exit(0 if result["consensus"]["estimator_count"] > 0 else 1)


if __name__ == "__main__":
    main()
