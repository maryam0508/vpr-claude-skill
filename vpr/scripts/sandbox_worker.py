#!/usr/bin/env python3
"""
VPR Sandbox Worker: Download, validate, extract, and convert papers to clean Markdown (.md).
Enforces:
1. Rate limit: Max 5 papers per run, 3s delay between network requests to protect upstream.
2. 4-rule strict validation (magic bytes, size, text length, title match).
3. PDF -> Markdown (.md) conversion for optimal LLM context ingestion.
4. Auto-cleanup: Deletes raw binary PDF files after text/markdown extraction to keep repo clean.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from typing import Dict, List, Optional, Tuple
from pypdf import PdfReader

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
MAX_PAPERS_PER_RUN = 5
RATE_LIMIT_DELAY = 3.0  # seconds

def clean_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        return ""
    arxiv_match = re.search(r'(?:arxiv\.org/(?:abs|pdf)/)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)', url, re.I)
    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    if not url.startswith(("http://", "https://")):
        if re.match(r'^[0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?$', url):
            return f"https://arxiv.org/pdf/{url}.pdf"
    return url

def download_pdf(url: str, output_path: str, timeout: int = 45) -> Tuple[bool, str]:
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            if not content.startswith(b"%PDF"):
                return False, "File does not start with %PDF header"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(content)
            return True, "OK"
    except Exception as e:
        return False, f"Download failed: {e}"

def convert_to_markdown(title: str, url: str, pages_text: List[str]) -> str:
    md_lines = [
        f"# {title}",
        f"",
        f"- **Source URL**: {url}",
        f"- **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"- **Total Pages**: {len(pages_text)}",
        f"- **Verification**: 4-Stage VPR Strict Validation Passed",
        f"",
        f"---",
        f""
    ]
    
    for idx, page_raw in enumerate(pages_text, start=1):
        clean_page = page_raw.strip()
        if not clean_page:
            continue
        md_lines.append(f"## Page {idx}")
        md_lines.append("")
        clean_page = re.sub(r'\n{3,}', '\n\n', clean_page)
        md_lines.append(clean_page)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        
    return "\n".join(md_lines)

def validate_and_extract(pdf_path: str, expected_title: Optional[str] = None) -> Tuple[bool, str, str, List[str]]:
    if not os.path.exists(pdf_path):
        return False, "File missing", "", []
    
    file_size = os.path.getsize(pdf_path)
    if file_size < 30_000:
        return False, f"File too small ({file_size} bytes < 30KB)", "", []

    with open(pdf_path, "rb") as f:
        magic = f.read(4)
        if magic != b"%PDF":
            return False, "Invalid PDF magic bytes", "", []

    try:
        reader = PdfReader(pdf_path)
        pages_text = []
        for p in reader.pages:
            t = p.extract_text() or ""
            pages_text.append(t)
        full_text = "\n\n".join(pages_text).strip()
    except Exception as e:
        return False, f"Corrupted PDF: {e}", "", []

    if len(full_text) < 2000:
        return False, f"Insufficient text ({len(full_text)} chars < 2000)", "", []

    norm = lambda s: re.sub(r'[^a-z0-9 ]', '', (s or "").lower())
    first_page_text = pages_text[0] if pages_text else ""
    first_lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
    detected_title = first_lines[0] if first_lines else "Untitled Paper"

    if expected_title and expected_title.strip():
        norm_expected = norm(expected_title).split()
        norm_first_page = norm(first_page_text)
        if norm_expected:
            hits = sum(1 for w in norm_expected if w in norm_first_page)
            overlap = hits / len(norm_expected)
            if overlap < 0.5:
                return False, f"Title mismatch with content (overlap {overlap:.2f} < 0.50)", detected_title, pages_text

    return True, "OK", detected_title, pages_text

def process_papers(urls: List[str], expected_title: Optional[str] = None, output_dir: str = "vpr_output"):
    os.makedirs(output_dir, exist_ok=True)
    md_dir = os.path.join(output_dir, "markdown")
    os.makedirs(md_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "_temp_pdf")
    os.makedirs(temp_dir, exist_ok=True)

    # Apply rate limit cap
    if len(urls) > MAX_PAPERS_PER_RUN:
        print(f"[RateLimit] Capped input from {len(urls)} to {MAX_PAPERS_PER_RUN} papers per execution.")
        urls = urls[:MAX_PAPERS_PER_RUN]

    extracted_papers: List[Dict] = []
    ledger: List[Dict] = []

    for idx, raw_url in enumerate(urls, start=1):
        target_url = clean_url(raw_url)
        if not target_url:
            continue
        
        pdf_path = os.path.join(temp_dir, f"paper_{idx}.pdf")
        md_filename = f"paper_{idx}.md"
        md_path = os.path.join(md_dir, md_filename)
        print(f"[{idx}/{len(urls)}] Processing: {target_url}")

        download_ok, download_reason = download_pdf(target_url, pdf_path)
        if not download_ok:
            print(f"  FAILED download: {download_reason}")
            ledger.append({
                "id": idx,
                "url": target_url,
                "status": "invalid",
                "reason": download_reason
            })
            continue

        valid, val_reason, det_title, pages_text = validate_and_extract(pdf_path, expected_title)
        file_size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0
        total_text_chars = sum(len(p) for p in pages_text)
        
        print(f"  Validation: {'SUCCESS' if valid else 'FAILED'} - {val_reason}")

        if valid:
            md_content = convert_to_markdown(det_title, target_url, pages_text)
            with open(md_path, "w", encoding="utf-8") as mdf:
                mdf.write(md_content)
            
            extracted_papers.append({
                "id": idx,
                "url": target_url,
                "title": det_title,
                "markdown_file": f"markdown/{md_filename}",
                "character_count": len(md_content),
                "total_pages": len(pages_text),
                "content_markdown": md_content
            })

            ledger.append({
                "id": idx,
                "url": target_url,
                "title": det_title,
                "markdown_file": f"markdown/{md_filename}",
                "pdf_size_bytes": file_size,
                "character_count": len(md_content),
                "status": "valid",
                "reason": val_reason
            })
        else:
            ledger.append({
                "id": idx,
                "url": target_url,
                "title": det_title or "Unknown",
                "pdf_size_bytes": file_size,
                "status": "invalid",
                "reason": val_reason
            })

        # AUTO-CLEANUP: Hapus file PDF biner agar tidak membebani repository GitHub
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
            print(f"  [Cleanup] Removed binary PDF: {pdf_path}")

        # Rate limit delay antar request
        if idx < len(urls):
            time.sleep(RATE_LIMIT_DELAY)

    # Hapus temp directory jika kosong
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

    # Save summary and JSONs
    extracted_path = os.path.join(output_dir, "extracted_papers.json")
    ledger_path = os.path.join(output_dir, "ledger.json")

    with open(extracted_path, "w", encoding="utf-8") as f:
        json.dump(extracted_papers, f, indent=2, ensure_ascii=False)

    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

    print(f"\nCompleted: {len(extracted_papers)}/{len(ledger)} papers validated and converted to Markdown.")
    print(f"All raw binary PDFs removed from disk. Markdown artifacts stored in: {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="VPR Sandbox Worker with Rate Limiting & Markdown Conversion")
    parser.add_argument("--urls", type=str, help="Comma or newline-separated paper URLs or arXiv IDs")
    parser.add_argument("--expected-title", type=str, default="", help="Expected title to verify against")
    parser.add_argument("--output-dir", type=str, default="vpr_output", help="Output directory for artifacts")
    args = parser.parse_args()

    urls = []
    if args.urls:
        urls.extend([u.strip() for u in re.split(r'[\r\n,]+', args.urls) if u.strip()])

    if not urls:
        print("Error: No URLs provided.")
        sys.exit(1)

    process_papers(urls, args.expected_title, args.output_dir)

if __name__ == "__main__":
    main()
