#!/usr/bin/env python3
"""
VPR Sandbox Worker: Download, validate, and extract paper text.
Adheres strictly to the 4 VPR validation rules.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from typing import Dict, List, Optional, Tuple
from pypdf import PdfReader

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"

def clean_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        return ""
    # ArXiv ID mapping to direct PDF
    arxiv_match = re.search(r'(?:arxiv\.org/(?:abs|pdf)/)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)', url, re.I)
    if arxiv_match:
        arxiv_id = arxiv_match.group(1)
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    if not url.startswith(("http://", "https://")):
        # If looks like arxiv id
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

def validate_and_extract(pdf_path: str, expected_title: Optional[str] = None) -> Tuple[bool, str, str, str]:
    """
    Validates PDF using 4 VPR rules:
    1. %PDF magic header
    2. Size > 30KB
    3. Extracted text > 2000 chars
    4. Expected title match (if provided)
    Returns: (is_valid, reason, extracted_title, full_text)
    """
    if not os.path.exists(pdf_path):
        return False, "File missing", "", ""
    
    file_size = os.path.getsize(pdf_path)
    if file_size < 30_000:
        return False, f"File too small ({file_size} bytes < 30KB)", "", ""

    with open(pdf_path, "rb") as f:
        magic = f.read(4)
        if magic != b"%PDF":
            return False, "Invalid PDF magic bytes", "", ""

    try:
        reader = PdfReader(pdf_path)
        pages_text = []
        for p in reader.pages:
            t = p.extract_text() or ""
            pages_text.append(t)
        full_text = "\n\n".join(pages_text).strip()
    except Exception as e:
        return False, f"Corrupted PDF: {e}", "", ""

    if len(full_text) < 2000:
        return False, f"Insufficient text ({len(full_text)} chars < 2000)", "", ""

    norm = lambda s: re.sub(r'[^a-z0-9 ]', '', (s or "").lower())
    first_page_text = pages_text[0] if pages_text else ""
    first_lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
    detected_title = first_lines[0] if first_lines else "Untitled"

    if expected_title and expected_title.strip():
        norm_expected = norm(expected_title).split()
        norm_first_page = norm(first_page_text)
        if norm_expected:
            hits = sum(1 for w in norm_expected if w in norm_first_page)
            overlap = hits / len(norm_expected)
            if overlap < 0.5:
                return False, f"Title mismatch with content (overlap {overlap:.2f} < 0.50)", detected_title, full_text

    return True, "OK", detected_title, full_text

def process_papers(urls: List[str], expected_title: Optional[str] = None, output_dir: str = "output"):
    os.makedirs(output_dir, exist_ok=True)
    papers_dir = os.path.join(output_dir, "papers")
    os.makedirs(papers_dir, exist_ok=True)

    extracted_papers: List[Dict] = []
    ledger: List[Dict] = []

    for idx, raw_url in enumerate(urls, start=1):
        target_url = clean_url(raw_url)
        if not target_url:
            continue
        
        pdf_filename = f"paper_{idx}.pdf"
        pdf_path = os.path.join(papers_dir, pdf_filename)
        print(f"[{idx}/{len(urls)}] Processing: {target_url}")

        download_ok, download_reason = download_pdf(target_url, pdf_path)
        if not download_ok:
            print(f"  FAILED download: {download_reason}")
            ledger.append({
                "id": idx,
                "url": target_url,
                "local_file": None,
                "status": "invalid",
                "reason": download_reason
            })
            continue

        valid, val_reason, det_title, text = validate_and_extract(pdf_path, expected_title)
        print(f"  Validation: {'SUCCESS' if valid else 'FAILED'} - {val_reason}")

        ledger_entry = {
            "id": idx,
            "url": target_url,
            "title": det_title or (expected_title if expected_title else "Unknown"),
            "local_file": pdf_path,
            "file_size": os.path.getsize(pdf_path),
            "text_length": len(text),
            "status": "valid" if valid else "invalid",
            "reason": val_reason
        }
        ledger.append(ledger_entry)

        if valid:
            extracted_papers.append({
                "id": idx,
                "url": target_url,
                "title": det_title,
                "text_length": len(text),
                "text": text
            })

    # Save results
    extracted_path = os.path.join(output_dir, "extracted_papers.json")
    ledger_path = os.path.join(output_dir, "ledger.json")

    with open(extracted_path, "w", encoding="utf-8") as f:
        json.dump(extracted_papers, f, indent=2, ensure_ascii=False)

    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

    print(f"Summary: {len(extracted_papers)}/{len(ledger)} papers validated successfully.")
    print(f"Artifacts written to: {output_dir}")

def main():
    parser = argparse.ArgumentParser(description="VPR Sandbox Worker")
    parser.add_argument("--urls", type=str, help="Comma or newline-separated paper URLs or arXiv IDs")
    parser.add_argument("--urls-file", type=str, help="Path to file containing URLs")
    parser.add_argument("--expected-title", type=str, default="", help="Expected title to verify against")
    parser.add_argument("--output-dir", type=str, default="vpr_output", help="Output directory for artifacts")
    args = parser.parse_args()

    urls = []
    if args.urls:
        urls.extend([u.strip() for u in re.split(r'[\r\n,]+', args.urls) if u.strip()])
    if args.urls_file and os.path.exists(args.urls_file):
        with open(args.urls_file, "r", encoding="utf-8") as f:
            urls.extend([line.strip() for line in f if line.strip()])

    if not urls:
        print("Error: No URLs provided.")
        sys.exit(1)

    process_papers(urls, args.expected_title, args.output_dir)

if __name__ == "__main__":
    main()
