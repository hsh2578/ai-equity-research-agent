"""후보 종목의 3M·12M·24M 상대강도를 한 번에 계산한다.

3개월만 보면 틀린다. 2026-08 실측 사례:
  대덕전자 3M −39%(RS −17)로 "아직 안 올랐다"고 보이지만 12M은 +347%(RS +234).
  급등 후 되돌림을 신규 기회로 착각하게 만든다.

따라서 판정은 12M·24M으로 하고 3M은 참고만 한다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta

WINDOWS = {"3M": 91, "12M": 365, "24M": 730}
HERE = os.path.dirname(os.path.abspath(__file__))
FETCH_QUOTE = os.path.join(HERE, "fetch_quote.py")


def run_window(codes: list[str], bench: str, start: str, end: str) -> list[dict]:
    """fetch_quote.py 를 호출해 한 구간의 수익률·상대강도를 받는다."""
    cmd = [sys.executable, FETCH_QUOTE, *codes, bench,
           "--start", start, "--end", end]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  {start}~{end} 조회 시간 초과", file=sys.stderr)
        return []
    if out.returncode != 0:
        print(f"  {start}~{end} 조회 실패: {out.stderr[:200]}", file=sys.stderr)
        return []
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        print(f"  {start}~{end} 응답 파싱 실패", file=sys.stderr)
        return []


def build(codes: list[str], bench: str, end: str, names: dict) -> list[dict]:
    end_d = date.fromisoformat(end)
    table: dict[str, dict] = {c: {"code": c, "name": names.get(c, c)} for c in codes}

    for label, days in WINDOWS.items():
        start = (end_d - timedelta(days=days)).isoformat()
        for r in run_window(codes, bench, start, end):
            code = r.get("code")
            if code not in table or r.get("return_pct") is None:
                continue
            table[code][label] = r["return_pct"]
            table[code][f"{label}_rs"] = r.get("relative_strength_pp")

    return list(table.values())


def verdict(row: dict) -> str:
    """12M·24M 상대강도로 판정. 둘 다 있어야 확정한다."""
    rs12, rs24 = row.get("12M_rs"), row.get("24M_rs")
    if rs12 is None and rs24 is None:
        return "데이터없음"
    vals = [v for v in (rs12, rs24) if v is not None]
    if max(vals) > 100:
        return "이미상승"
    if min(vals) < -50:
        return "미반영"
    return "중립"


def main() -> None:
    ap = argparse.ArgumentParser(description="다기간 상대강도 표")
    ap.add_argument("codes", nargs="+", help="종목코드 (6자리)")
    ap.add_argument("--bench", default="KOSPI", help="벤치마크 (기본 KOSPI)")
    ap.add_argument("--end", default=date.today().isoformat(), help="기준일 YYYY-MM-DD")
    ap.add_argument("--names", default="", help='별칭 JSON: {"005930":"삼성전자"}')
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    names = json.loads(args.names) if args.names else {}
    rows = build(args.codes, args.bench, args.end, names)
    rows.sort(key=lambda r: (r.get("24M_rs") if r.get("24M_rs") is not None else 1e9))

    print(f"기준일 {args.end} · 벤치마크 {args.bench}")
    print(f"{'종목':<16}{'24M':>8}{'RS':>7}{'12M':>8}{'RS':>7}{'3M':>7}{'RS':>6}  판정")
    for r in rows:
        def f(k, w, suffix=""):
            v = r.get(k)
            return f"{v:>{w}.0f}{suffix}" if v is not None else f"{'—':>{w}}{suffix}"
        print(f"{r['name'][:15]:<16}{f('24M', 7, '%')}{f('24M_rs', 7)}"
              f"{f('12M', 7, '%')}{f('12M_rs', 7)}"
              f"{f('3M', 6, '%')}{f('3M_rs', 6)}  {verdict(r)}")

    print("\n판정 기준: 12M·24M RS 중 최대 > +100 → 이미상승 / 최소 < −50 → 미반영")
    print("3M 단독 판정 금지 — 급등 후 되돌림을 신규 기회로 오인한다.")


if __name__ == "__main__":
    main()
