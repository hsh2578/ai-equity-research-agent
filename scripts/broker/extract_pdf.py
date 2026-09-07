"""한경 PDF 다운로드 + 전문(全文) 텍스트 추출 + 프라이버시 정제.

전문을 추출해 reports_text/{idx}.txt 로 저장하고 메타데이터(JSON)를 출력한다.
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import urllib.request

import pypdf

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PDF_URL = "https://consensus.hankyung.com/analysis/downpdf?report_idx={idx}"

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL = re.compile(r"https?://\S+")


def clean_text(text: str) -> str:
    text = _EMAIL.sub(" ", text)
    text = _URL.sub(" ", text)
    text = text.replace("?", " ").replace("&", " ").replace("=", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_too_short(pages: int, floor: int = 5) -> bool:
    return pages < floor


def download_pdf(idx: str) -> bytes:
    url = PDF_URL.format(idx=idx)
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()


def extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages = len(reader.pages)
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    return clean_text(text), pages


def fetch_and_save(idx: str, out_dir: str = "reports_text") -> dict:
    os.makedirs(out_dir, exist_ok=True)
    text, pages = extract_text(download_pdf(idx))
    path = os.path.join(out_dir, f"{idx}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return {
        "idx": idx,
        "pages": pages,
        "chars": len(text),
        "path": path,
        "too_short": is_too_short(pages),
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    idx = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "reports_text"
    print(json.dumps(fetch_and_save(idx, out_dir), ensure_ascii=False))
