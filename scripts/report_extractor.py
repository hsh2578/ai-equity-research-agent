"""
사업보고서 핵심 문장 자동 추출기

사업보고서를 읽고 리포트에 반드시 인용해야 할 핵심 문장들을 추출합니다.
이 스크립트의 출력물이 analysis.json에 반영되지 않으면 리포트 품질이 보장되지 않습니다.

사용법:
  python scripts/report_extractor.py data/LS/data_dart_reports.json
  → data/LS/report_quotes.json 생성
"""

import json
import sys
import re
import os


def extract_key_quotes(reports_path: str) -> dict:
    """
    사업보고서에서 핵심 인용 문장을 자동 추출합니다.

    추출 대상:
    1. 사업 구조 설명 (세그먼트, 매출 비중)
    2. 위험 요인 (회사가 직접 인정한 리스크)
    3. 주요 계약/수주
    4. 경영진 전략 방향
    5. 전년 대비 변화점
    """
    with open(reports_path, "r", encoding="utf-8") as f:
        reports = json.load(f)

    result = {
        "latest_report": {},
        "prev_report": {},
        "key_quotes": [],
        "yoy_changes": [],
        "segment_data": "",
        "risk_factors": [],
        "major_contracts": [],
        "rd_highlights": [],
    }

    # 최신 사업보고서와 전년 사업보고서 분리
    annual_reports = [r for r in reports if r["type"] == "사업보고서"]
    if not annual_reports:
        annual_reports = reports[:1]  # 없으면 첫 번째라도

    latest = annual_reports[0] if annual_reports else None
    prev = annual_reports[1] if len(annual_reports) > 1 else None

    if latest:
        result["latest_report"] = {
            "type": latest["type"],
            "date": latest["rcept_dt"],
            "name": latest["report_nm"],
        }

    if prev:
        result["prev_report"] = {
            "type": prev["type"],
            "date": prev["rcept_dt"],
            "name": prev["report_nm"],
        }

    # === 1. 사업 구조 (세그먼트) ===
    if latest:
        biz = latest["sections"].get("사업의_내용", "")
        # 세그먼트/부문 관련 문장 추출
        for pattern in [r'\d+%', r'부문', r'세그먼트', r'매출.*비중', r'사업.*구성']:
            matches = list(re.finditer(pattern, biz))
            for m in matches[:3]:
                start = max(0, m.start() - 100)
                end = min(len(biz), m.end() + 200)
                snippet = biz[start:end].strip()
                # 줄바꿈 정리
                snippet = re.sub(r'\s+', ' ', snippet)
                if len(snippet) > 30:
                    result["segment_data"] = snippet
                    break
            if result["segment_data"]:
                break

    # === 2. 위험 요인 ===
    if latest:
        risk = latest["sections"].get("위험_요인", "")
        if risk:
            # 위험 항목 번호 패턴으로 분리
            risk_items = re.split(r'\(\d+\)|\d+\)', risk)
            for item in risk_items[:5]:
                item = re.sub(r'\s+', ' ', item.strip())
                if len(item) > 50:
                    result["risk_factors"].append(item[:300])

    # === 3. 주요 계약 ===
    if latest:
        contracts = latest["sections"].get("주요_계약", "")
        if contracts:
            # 금액이 포함된 문장 추출
            for pattern in [r'억원', r'조원', r'USD', r'계약', r'수주', r'공급']:
                for m in re.finditer(pattern, contracts):
                    start = max(0, m.start() - 80)
                    end = min(len(contracts), m.end() + 150)
                    snippet = re.sub(r'\s+', ' ', contracts[start:end].strip())
                    if len(snippet) > 30 and snippet not in result["major_contracts"]:
                        result["major_contracts"].append(snippet[:250])
                        if len(result["major_contracts"]) >= 5:
                            break
                if len(result["major_contracts"]) >= 5:
                    break

    # === 4. 연구개발 ===
    if latest:
        rd = latest["sections"].get("연구개발", "")
        if rd:
            for pattern in [r'개발', r'특허', r'기술', r'R&D', r'연구']:
                for m in re.finditer(pattern, rd):
                    start = max(0, m.start() - 50)
                    end = min(len(rd), m.end() + 200)
                    snippet = re.sub(r'\s+', ' ', rd[start:end].strip())
                    if len(snippet) > 50:
                        result["rd_highlights"].append(snippet[:250])
                        if len(result["rd_highlights"]) >= 3:
                            break
                if len(result["rd_highlights"]) >= 3:
                    break

    # === 5. 전년 대비 변화점 ===
    if latest and prev:
        latest_biz = latest["sections"].get("사업의_내용", "")
        prev_biz = prev["sections"].get("사업의_내용", "")

        # 길이 변화
        len_diff = len(latest_biz) - len(prev_biz)
        if abs(len_diff) > 500:
            result["yoy_changes"].append(
                f"사업의 내용 분량이 전년 대비 {'증가' if len_diff > 0 else '감소'}({abs(len_diff)}자 차이) — 사업 설명이 {'확대' if len_diff > 0 else '축소'}됨"
            )

        # 위험 요인 비교
        latest_risk = latest["sections"].get("위험_요인", "")
        prev_risk = prev["sections"].get("위험_요인", "")
        risk_len_diff = len(latest_risk) - len(prev_risk)
        if abs(risk_len_diff) > 300:
            result["yoy_changes"].append(
                f"위험 요인 분량이 전년 대비 {'증가' if risk_len_diff > 0 else '감소'}({abs(risk_len_diff)}자 차이) — 리스크 인식이 {'강화' if risk_len_diff > 0 else '완화'}됨"
            )

        # 새로운 키워드 등장
        new_keywords = []
        check_words = ["AI", "데이터센터", "ESG", "탄소", "수소", "전고체", "M&A", "합병", "인수", "매각", "구조조정", "리스크"]
        for word in check_words:
            if word in latest_biz and word not in prev_biz:
                new_keywords.append(word)
        if new_keywords:
            result["yoy_changes"].append(
                f"올해 사업보고서에 새로 등장한 키워드: {', '.join(new_keywords)}"
            )

    # === 핵심 인용 문장 종합 ===
    if result["segment_data"]:
        result["key_quotes"].append({
            "source": "사업의 내용",
            "quote": result["segment_data"],
            "usage": "s03 회사개요에서 세그먼트 구조 인용"
        })

    for rf in result["risk_factors"][:2]:
        result["key_quotes"].append({
            "source": "위험 요인",
            "quote": rf,
            "usage": "s08 재무분석 또는 s14 숏논거에서 리스크 인용"
        })

    for mc in result["major_contracts"][:2]:
        result["key_quotes"].append({
            "source": "주요 계약",
            "quote": mc,
            "usage": "s11 카탈리스트 또는 s02 투자포인트에서 인용"
        })

    for rd in result["rd_highlights"][:1]:
        result["key_quotes"].append({
            "source": "연구개발",
            "quote": rd,
            "usage": "s06 경제적 해자에서 기술 경쟁력 인용"
        })

    for change in result["yoy_changes"]:
        result["key_quotes"].append({
            "source": "전년 대비 변화",
            "quote": change,
            "usage": "s08 재무분석에서 전년 대비 변화 언급"
        })

    return result


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/report_extractor.py data/{종목}/data_dart_reports.json")
        sys.exit(1)

    reports_path = sys.argv[1]
    result = extract_key_quotes(reports_path)

    # 저장
    output_dir = os.path.dirname(reports_path)
    output_path = os.path.join(output_dir, "report_quotes.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 출력
    print(f"\n{'='*60}")
    print(f"  사업보고서 핵심 추출 완료")
    print(f"{'='*60}")
    print(f"\n최신 보고서: {result['latest_report'].get('name', 'N/A')}")
    print(f"전년 보고서: {result['prev_report'].get('name', 'N/A')}")
    print(f"\n=== 반드시 인용해야 할 문장 ({len(result['key_quotes'])}개) ===\n")

    for i, q in enumerate(result["key_quotes"], 1):
        print(f"[{i}] 출처: {q['source']}")
        print(f"    인용: {q['quote'][:100]}...")
        print(f"    용도: {q['usage']}")
        print()

    print(f"전년 대비 변화점: {len(result['yoy_changes'])}개")
    for c in result["yoy_changes"]:
        print(f"  - {c}")

    print(f"\n저장: {output_path}")


if __name__ == "__main__":
    main()
