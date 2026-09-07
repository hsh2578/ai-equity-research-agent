"""리포트 목록 JSON -> PDF 대량 다운로드 + 2단 텍스트 저장 + 매니페스트.

extract_pdf 의 download/extract/clean 을 재사용하며, 리포트당 두 파일을 쓴다.
  {idx}.txt       전문 (심층 정독용)
  {idx}.head.txt  앞 HEAD_CHARS 자 (전수 스킴용 — 예산을 결정론적으로 고정)

재개 가능: {idx}.txt 가 이미 있으면 건너뛴다. 개별 실패는 삼키고 매니페스트에 기록.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_pdf import PDF_URL, download_pdf, extract_text, is_too_short  # noqa: E402

HEAD_CHARS = 3500

# 리포트 앞부분을 잠식하는 면책/컴플라이언스 상투구. head 슬라이스 품질을 위해 제거한다
# (전문 {idx}.txt 는 손대지 않는다 — 심층 정독은 원문 그대로 읽어야 하므로).
_BOILERPLATE = (
    "조사분석자료", "투자참고 자료", "법적 책임소재", "compliance notice", "준법감시",
    "본인의 의견을 정확하게", "외부의 부당한 압력", "지분을 보유하고 있지 않",
    "어떠한 경우에도", "금융투자업규정", "고지의무", "신뢰할 만한 자료",
    "정확성이나 완전성을 보장", "당사와 관련이 없음을", "무단 복제", "인용하실 수 없",
    "본 자료는 기관투자가", "제공된 자료입니다", "매매를 권유하는", "이용하시는 분에게",
)


def strip_boilerplate(text: str) -> str:
    """면책 문구 줄과 빈 줄을 걷어낸다. 본문 라인 순서는 보존."""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(kw in low for kw in _BOILERPLATE):
            continue
        out.append(s)
    return "\n".join(out)

# 한경은 동시 요청이 많으면 IP 단위로 403 을 건다(실측: 동시성 11로 ~900건 → 전면 차단).
# 요청 간 지연 + 지수 백오프 재시도로 정중하게 받는다.
RETRY_WAITS = (30, 90, 240, 600)

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
       "Referer": "https://finance.naver.com/research/"}


def download_url(url: str) -> bytes:
    """임의 URL에서 PDF를 받는다 (네이버 stock.pstatic.net 등 직접 링크용)."""
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=90).read()


def pdf_target(meta: dict) -> str:
    """리포트 메타에서 다운로드 대상 URL을 고른다. pdf_url 이 있으면 그것을 쓴다."""
    url = meta.get("pdf_url")
    if url:
        return url
    return PDF_URL.format(idx=meta["report_idx"])


def polite_downloader(delay: float = 0.4, retry_waits=RETRY_WAITS, sleep=time.sleep):
    """URL 다운로드에 지연·재시도를 붙인 다운로더를 만든다."""
    def _dl(url: str) -> bytes:
        last = None
        for attempt in range(len(retry_waits) + 1):
            try:
                if delay:
                    sleep(delay)
                return download_url(url)
            except Exception as exc:                # HTTPError 403/429/5xx 포함
                last = exc
                code = getattr(exc, "code", None)
                if code is not None and code not in (403, 429, 500, 502, 503, 504):
                    raise
                if attempt < len(retry_waits):
                    sleep(retry_waits[attempt])
        raise last
    return _dl


MANIFEST_FIELDS = [
    "idx", "date", "category", "sector", "publisher", "author", "title",
    "pages", "chars", "too_short", "ok", "error",
]


def head_slice(text: str, limit: int = HEAD_CHARS) -> str:
    return strip_boilerplate(text)[:limit]


def save_one(meta: dict, out_dir: str, limit: int = HEAD_CHARS, downloader=None) -> dict:
    """리포트 1건을 받아 전문/head 를 저장하고 매니페스트 행(dict)을 돌려준다.

    이미 {idx}.txt 가 있으면 다운로드하지 않고 디스크에서 재구성한다(재개).
    """
    idx = str(meta["report_idx"])
    row = {
        "idx": idx,
        "date": meta.get("date", ""),
        "category": meta.get("category", ""),
        "publisher": meta.get("publisher", ""),
        "sector": meta.get("sector", ""),
        "author": meta.get("author", ""),
        "title": meta.get("title", ""),
        "pages": "", "chars": "", "too_short": "", "ok": False, "error": "",
    }
    full_path = os.path.join(out_dir, f"{idx}.txt")
    head_path = os.path.join(out_dir, f"{idx}.head.txt")
    meta_path = os.path.join(out_dir, f"{idx}.meta.json")

    try:
        if os.path.exists(full_path) and os.path.exists(meta_path):
            with open(meta_path, encoding="utf-8") as f:
                cached = json.load(f)
            row.update(pages=cached["pages"], chars=cached["chars"],
                       too_short=cached["too_short"], ok=True)
            return row

        dl = downloader or download_url
        text, pages = extract_text(dl(pdf_target(meta)))
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(text)
        with open(head_path, "w", encoding="utf-8") as f:
            f.write(head_slice(text, limit))
        short = is_too_short(pages)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"pages": pages, "chars": len(text), "too_short": short},
                      f, ensure_ascii=False)
        row.update(pages=pages, chars=len(text), too_short=short, ok=True)
    except Exception as exc:                      # 개별 실패가 전체를 죽이지 않게
        row["error"] = f"{type(exc).__name__}: {exc}"[:200]
    return row


def run(reports: list[dict], out_dir: str, workers: int = 6,
        limit: int = HEAD_CHARS, downloader=None, progress=None) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    rows: list[dict] = []
    lock = threading.Lock()
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        dl = downloader or polite_downloader()
        futs = {ex.submit(save_one, m, out_dir, limit, dl): m for m in reports}
        for fut in as_completed(futs):
            row = fut.result()
            with lock:
                rows.append(row)
                done += 1
                if progress and done % 25 == 0:
                    progress(done, len(reports))
    order = {str(m["report_idx"]): i for i, m in enumerate(reports)}
    rows.sort(key=lambda r: order.get(r["idx"], 10**9))
    return rows


def write_manifest(rows: list[dict], path: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in MANIFEST_FIELDS})
    return path


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(description="리포트 목록 JSON 대량 다운로드")
    p.add_argument("list_json", help="fetch_range.py 가 만든 JSON")
    p.add_argument("--out", default="_scout/text")
    p.add_argument("--manifest", default=None, help="기본: <out>/../manifest.csv")
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--delay", type=float, default=0.4, help="요청 간 지연(초)")
    p.add_argument("--head-chars", type=int, default=HEAD_CHARS)
    p.add_argument("--limit", type=int, default=0, help="앞 N건만 (스모크 테스트용)")
    p.add_argument("--rebuild-heads", action="store_true",
                   help="다운로드 없이, 저장된 전문에서 head 슬라이스만 다시 만든다")
    a = p.parse_args(argv)

    with open(a.list_json, encoding="utf-8") as f:
        reports = json.load(f)["reports"]
    if a.limit:
        reports = reports[: a.limit]

    if a.rebuild_heads:
        n = 0
        for m in reports:
            idx = str(m["report_idx"])
            full = os.path.join(a.out, f"{idx}.txt")
            if not os.path.exists(full):
                continue
            with open(full, encoding="utf-8") as f:
                text = f.read()
            with open(os.path.join(a.out, f"{idx}.head.txt"), "w", encoding="utf-8") as f:
                f.write(head_slice(text, a.head_chars))
            n += 1
        print(json.dumps({"rebuilt_heads": n}, ensure_ascii=False))
        return 0

    def _progress(done: int, total: int) -> None:
        print(f"  {done}/{total}", file=sys.stderr)

    rows = run(reports, a.out, workers=a.workers, limit=a.head_chars,
               downloader=polite_downloader(delay=a.delay), progress=_progress)
    manifest = a.manifest or os.path.join(os.path.dirname(os.path.abspath(a.out)), "manifest.csv")
    write_manifest(rows, manifest)

    ok = sum(1 for r in rows if r["ok"])
    short = sum(1 for r in rows if r["ok"] and r["too_short"])
    print(json.dumps({
        "total": len(rows), "ok": ok, "failed": len(rows) - ok,
        "too_short": short, "usable": ok - short, "manifest": manifest,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    raise SystemExit(main(sys.argv[1:]))
