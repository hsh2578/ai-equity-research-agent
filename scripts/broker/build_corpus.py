"""수집한 원문에서 중복을 제거하고 병목 판정용 발췌본을 만든다.

오늘의 실측: 원문 2,607편 중 469편(18.0%)이 md5 동일한 중복본이었다.
중복을 먼저 걷어내지 않으면 서브에이전트가 같은 리포트를 두 번 읽는다.

발췌본은 요약이 아니라 '병목 근거가 실릴 자리'를 우선 담은 절단본이다.
앞부분만 자르면 개별 기업분석 섹션(뒤쪽)이 통째로 날아가므로,
병목 키워드가 있는 문단을 먼저 채우고 남은 예산을 앞부분으로 채운다.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys

# 병목 근거가 실리는 문장에 실제로 등장한 표현들 (2026-08 코퍼스에서 추출)
SIGNAL = re.compile(
    r"리드\s?타임|납기|가동률|풀\s?캐파|캐파|CAPA|수주\s?잔고|점유율|M/S|"
    r"공급\s?부족|공급\s?제약|쇼티지|품절|재고\s?소진|병목|"
    r"BB\s?Ratio|판가|가격\s?인상|증설|단일\s?공급|과점|독점|"
    r"수요가\s?공급|초과|타이트",
    re.I,
)

# 리포트 말미 면책·조사분석 고지. 발췌본 예산을 갉아먹으므로 제거한다.
BOILERPLATE = re.compile(
    r"조사분석자료|투자참고\s?자료|법적\s?책임|compliance\s?notice|"
    r"준법감시|본\s?자료는|무단\s?복제|투자등급|목표주가\s?변동",
    re.I,
)

DEFAULT_BUDGET = 16000  # 3,500자로는 병목 근거가 잘렸다. 16,000자가 실측 하한.


def file_hash(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def find_duplicates(paths: list[str]) -> dict[str, list[str]]:
    """md5가 같은 파일을 묶는다. 값의 첫 원소가 대표본."""
    groups: dict[str, list[str]] = {}
    for p in paths:
        try:
            groups.setdefault(file_hash(p), []).append(p)
        except OSError as e:
            print(f"  건너뜀 {os.path.basename(p)}: {e}", file=sys.stderr)
    return groups


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def excerpt(text: str, budget: int = DEFAULT_BUDGET) -> str:
    """병목 신호가 있는 문단을 우선 담고, 남으면 앞부분으로 채운다.

    빈 줄 없이 한 덩어리로 추출된 PDF가 있다. 그 경우 문단이 1개뿐이고
    길이가 예산을 넘어 통째로 버려지면 발췌본이 빈 파일이 된다(실측: 125편 중 4편).
    예산을 넘는 문단은 버리지 않고 잘라 담는다.
    """
    paras = [p for p in split_paragraphs(text) if not BOILERPLATE.search(p)]
    if not paras:
        return text[:budget]

    signal_idx = [i for i, p in enumerate(paras) if SIGNAL.search(p)]
    picked: dict[int, str] = {}
    used = 0

    def take(i: int) -> bool:
        """남은 예산만큼 담는다. 문단이 길면 잘라서라도 담는다."""
        nonlocal used
        if i in picked:
            return False
        room = budget - used
        if room < 200:          # 문장 하나도 못 담을 잔여 예산
            return False
        body = paras[i][:room - 2]
        picked[i] = body
        used += len(body) + 2
        return True

    for i in signal_idx:        # 1순위: 병목 신호 문단
        take(i)
    for i in range(len(paras)):  # 2순위: 앞부분(요약·투자포인트)
        take(i)

    out = "\n\n".join(picked[i] for i in sorted(picked))

    # 최후 안전망: 그래도 비면 원문 앞부분을 그대로 쓴다
    if len(out) < min(budget // 8, len(text) // 2):
        return text[:budget]
    return out


def build(text_dir: str, budget: int, keep_duplicates: bool) -> dict:
    raw = [
        os.path.join(text_dir, f)
        for f in sorted(os.listdir(text_dir))
        if f.endswith(".txt")
        and not any(m in f for m in (".head.", ".sum.", ".big.", ".meta."))
    ]
    if not raw:
        print(f"원문 없음: {text_dir}", file=sys.stderr)
        return {"total": 0, "unique": 0, "written": 0}

    groups = find_duplicates(raw)
    dup_count = len(raw) - len(groups)

    targets = raw if keep_duplicates else [g[0] for g in groups.values()]
    dropped = []
    if not keep_duplicates:
        for g in groups.values():
            dropped.extend(os.path.basename(p)[:-4] for p in g[1:])

    written = 0
    thin = []  # 원문은 충분한데 발췌가 비정상적으로 짧은 건 — 추출 실패 신호
    for p in targets:
        try:
            text = open(p, encoding="utf-8").read()
        except OSError as e:
            print(f"  읽기 실패 {os.path.basename(p)}: {e}", file=sys.stderr)
            continue
        body = excerpt(text, budget)
        with open(p[:-4] + ".sum.txt", "w", encoding="utf-8") as f:
            f.write(body)
        written += 1
        if len(text) > 5000 and len(body) < 1000:
            thin.append((os.path.basename(p)[:-4], len(text), len(body)))

    return {
        "total": len(raw),
        "unique": len(groups),
        "duplicates": dup_count,
        "written": written,
        "dropped": dropped,
        "thin": thin,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="중복 제거 + 병목 발췌본 생성")
    ap.add_argument("text_dir", help="원문 {idx}.txt 가 있는 디렉터리")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help=f"발췌본 글자수 (기본 {DEFAULT_BUDGET})")
    ap.add_argument("--keep-duplicates", action="store_true",
                    help="중복본도 발췌본을 만든다 (기본은 대표본 1개만)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    r = build(args.text_dir, args.budget, args.keep_duplicates)
    if not r["total"]:
        raise SystemExit(1)

    pct = r["duplicates"] / r["total"] * 100
    print(f"원문 {r['total']}편 → 고유 {r['unique']}편 "
          f"(중복 {r['duplicates']}편, {pct:.1f}%)")
    print(f"발췌본 {r['written']}개 생성 (편당 최대 {args.budget:,}자)")
    if r["dropped"]:
        head = ", ".join(r["dropped"][:8])
        more = f" 외 {len(r['dropped']) - 8}편" if len(r["dropped"]) > 8 else ""
        print(f"중복으로 제외: {head}{more}")

    if r["thin"]:
        print(f"\n경고 — 발췌가 비정상적으로 짧은 {len(r['thin'])}편 (PDF 추출 확인 필요):")
        for idx, src, got in r["thin"]:
            print(f"  {idx}: 원문 {src:,}자 → 발췌 {got}자")
        print("서브에이전트에 넘기기 전에 원문을 직접 확인한다.")


if __name__ == "__main__":
    main()
