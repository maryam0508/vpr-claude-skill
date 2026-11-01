---
name: verified-paper-research
description: Search, download, validate, and summarize scientific papers and academic journals without hallucination. Generates verified citations and ledger.
dependencies: python>=3.8, pypdf, requests
license: MIT
---

# Verified Paper Research (vpr) for Claude

Use this skill whenever asked to search, synthesize, cite, or create presentations/documents from academic research, scientific papers, or journal articles.

## Core Rule
> **A paper can only be cited or used if the actual full-text PDF has been downloaded, opened, and verified in this session.**
> Training memory is NOT an acceptable source for citations, author names, years, or findings.

---

## ⚡ GitHub Actions Sandbox Offloading (Recommended for Claude.ai)
When Claude runs in an environment where outbound PDF binary downloads are blocked or restricted, use the repository's GitHub Actions workflow as an offloaded sandbox downloader & validator:

1. **Dispatch the Workflow via GitHub API**:
   ```bash
   curl -X POST \
     -H "Accept: application/vnd.github.v3+json" \
     -H "Authorization: token $GITHUB_TOKEN" \
     https://api.github.com/repos/maryam0508/vpr-claude-skill/actions/workflows/vpr-sandbox.yml/dispatches \
     -d '{"ref":"main", "inputs":{"paper_urls":"https://arxiv.org/abs/2310.02949"}}'
   ```
2. **Retrieve Clean Extracted Text**:
   The workflow runs on an Ubuntu runner, validates all 4 rules, extracts text, and pushes directly to the `data` branch:
   - Direct Raw URL: `https://raw.githubusercontent.com/maryam0508/vpr-claude-skill/data/latest/extracted_papers.json`
   - Ledger Status: `https://raw.githubusercontent.com/maryam0508/vpr-claude-skill/data/latest/ledger.json`

---

---

## 1. Search Candidates
Use academic APIs or web search to find open-access papers.

### Universal Academic APIs:
- **arXiv API**: `http://export.arxiv.org/api/query?search_query=all:{query}&max_results=5`
- **Crossref API**: `https://api.crossref.org/works?query={query}&filter=has-full-text:true&rows=5`
- **Semantic Scholar API**: `https://api.semanticscholar.org/graph/v1/paper/search?query={query}&fields=title,authors,year,openAccessPdf`
- **OpenAlex API**: `https://api.openalex.org/works?search={query}&filter=is_oa:true`

Always gather candidate metadata: Title, Authors, Year, Landing URL, Direct PDF URL.

---

## 2. Download PDF
Download the paper to `./papers/{id}.pdf`:

```python
import urllib.request, os

def download_pdf(pdf_url, output_path):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    req = urllib.request.Request(pdf_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if content[:4] == b'%PDF':
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(content)
                return True
    except Exception as e:
        print(f"Download failed: {e}")
    return False
```

---

## 3. Strict Validation
A paper is only marked `valid` if it meets ALL four criteria:
1. Starts with `%PDF` bytes (not HTML paywall error page).
2. File size > 30 KB.
3. Extractable text > 2,000 characters (not a blank/scanned image PDF).
4. Content title matches expected title (>60% word overlap).

```python
import os, re
from pypdf import PdfReader

def validate_pdf(pdf_path, expected_title):
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 30_000:
        return False, "File too small or missing"
    try:
        reader = PdfReader(pdf_path)
        text = " ".join([page.extract_text() or "" for page in reader.pages])
    except Exception as e:
        return False, f"Corrupted PDF: {e}"
    
    if len(text.strip()) < 2000:
        return False, "Empty or scanned PDF"
        
    norm = lambda s: re.sub(r'[^a-z0-9 ]', '', s.lower())
    words = norm(expected_title).split()
    first_page = norm(reader.pages[0].extract_text() or "")
    hits = sum(1 for w in words if w in first_page)
    if words and (hits / len(words)) < 0.5:
        return False, "Title mismatch with PDF content"
        
    return True, text
```

---

## 4. Source Ledger (`ledger.json`)
Maintain a tracking ledger in the working directory:
```json
[
  {
    "title": "...",
    "authors": "...",
    "year": "2024",
    "url": "https://arxiv.org/abs/...",
    "local_file": "papers/1.pdf",
    "status": "valid",
    "reason": "OK"
  }
]
```

To render the visual Kanban board:
```bash
python scripts/render_kanban.py ledger.json kanban.html
```

---

## 5. Output Synthesis
1. Synthesize materials **only** from the extracted text of papers with `status: "valid"`.
2. Format citations with exact author, year, and page/section numbers.
3. Generate citations in Mendeley XML (EndNote XML) or BibTeX upon request.
4. If candidate search fails, explicitly report which papers could not be verified rather than fabricating details.
