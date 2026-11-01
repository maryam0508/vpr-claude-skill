#!/usr/bin/env python3
"""
VPR MCP Server: Model Context Protocol (stdio transport) server for Claude / AI Assistants.
Provides tools:
1. vpr_search_candidates(query, max_results): Search open-access papers via arXiv API.
2. vpr_trigger_sandbox(paper_urls, expected_title): Trigger GitHub Actions workflow or fallback locally.
3. vpr_fetch_verified_markdown(paper_id_or_url): Fetch verified markdown text from branch 'data' or local storage.
4. vpr_local_research(query, max_papers): Local crawling, validation, and markdown conversion (Docker/local).
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

SERVER_NAME = "vpr-mcp-server"
SERVER_VERSION = "1.0.1"
PROTOCOL_VERSION = "2024-11-05"

DEFAULT_REPO = "maryam0508/vpr-claude-skill"
WORKFLOW_FILE = "vpr-sandbox.yml"
RAW_DATA_BASE_URL = f"https://raw.githubusercontent.com/{DEFAULT_REPO}/data"
USER_AGENT = "VPR-MCPServer/1.0.1 (+https://github.com/maryam0508/vpr-claude-skill)"

# Rate Limiter: Max 3 crawling/search requests per 90 seconds (1.5 min)
RATE_LIMIT_MAX_REQUESTS = 3
RATE_LIMIT_WINDOW_SECONDS = 90.0
_request_timestamps: List[float] = []


def log(msg: str) -> None:
    sys.stderr.write(f"[vpr-mcp] {msg}\n")
    sys.stderr.flush()


def check_rate_limit() -> Optional[Dict[str, Any]]:
    """Enforce maximum 3 crawling/search requests within 90 seconds (1.5 minutes)."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    global _request_timestamps
    _request_timestamps = [t for t in _request_timestamps if t > cutoff]

    if len(_request_timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        earliest = _request_timestamps[0]
        retry_after = int(RATE_LIMIT_WINDOW_SECONDS - (now - earliest)) + 1
        return {
            "status": "rate_limited",
            "error": f"Rate limit exceeded: Max {RATE_LIMIT_MAX_REQUESTS} requests per {int(RATE_LIMIT_WINDOW_SECONDS)}s (1.5 min).",
            "retry_after_seconds": max(1, retry_after),
            "window_seconds": int(RATE_LIMIT_WINDOW_SECONDS),
        }
    _request_timestamps.append(now)
    return None


def tool_search_candidates(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search arXiv API for academic papers matching the query with rate limiting."""
    limit_check = check_rate_limit()
    if limit_check:
        return limit_check

    max_res = max(1, min(int(max_results), 10))
    encoded_query = urllib.parse.quote(query.strip())
    url = f"https://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={max_res}&sortBy=relevance&sortOrder=descending"

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    except Exception as e:
        return {"error": f"Failed to query arXiv API: {e}", "candidates": []}

    try:
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        candidates: List[Dict[str, Any]] = []

        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", namespaces=ns) or ""
            title = re.sub(r"\s+", " ", title).strip()

            summary = entry.findtext("atom:summary", namespaces=ns) or ""
            summary = re.sub(r"\s+", " ", summary).strip()

            published = entry.findtext("atom:published", namespaces=ns) or ""
            published_year = published[:4] if len(published) >= 4 else "unknown"

            entry_id = entry.findtext("atom:id", namespaces=ns) or ""
            arxiv_id_match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", entry_id)
            arxiv_id = arxiv_id_match.group(1) if arxiv_id_match else ""

            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                    pdf_url = link.get("href", "")
                    break

            if not pdf_url and arxiv_id:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            authors = [
                author.findtext("atom:name", namespaces=ns) or ""
                for author in entry.findall("atom:author", ns)
            ]

            candidates.append({
                "title": title,
                "arxiv_id": arxiv_id,
                "authors": [a for a in authors if a],
                "year": published_year,
                "summary": summary[:300] + "..." if len(summary) > 300 else summary,
                "pdf_url": pdf_url,
                "entry_url": entry_id,
            })

        return {
            "query": query,
            "total_found": len(candidates),
            "candidates": candidates,
        }
    except Exception as e:
        return {"error": f"Failed to parse arXiv response: {e}", "candidates": []}


def tool_trigger_sandbox(paper_urls: str, expected_title: str = "") -> Dict[str, Any]:
    """
    Trigger GitHub Actions workflow dispatch or run in Free MCP Mode if no token provided.
    """
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    # Free MCP Mode: if token is absent, run local research directly
    if not github_token:
        log("GITHUB_TOKEN not detected. Executing in Free MCP Mode (local pipeline).")
        urls = [u.strip() for u in re.split(r"[\n,]+", paper_urls.strip()) if u.strip()]
        return run_local_pipeline(urls, expected_title=expected_title)

    repo = os.environ.get("VPR_GITHUB_REPO", DEFAULT_REPO)
    api_url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches"

    payload = {
        "ref": "main",
        "inputs": {
            "paper_urls": paper_urls.strip(),
            "expected_title": expected_title.strip(),
        },
    }

    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(api_url, data=req_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status_code = resp.status
            if status_code in (204, 201, 200):
                return {
                    "success": True,
                    "mode": "cloud_github_actions",
                    "message": f"Successfully triggered workflow '{WORKFLOW_FILE}' on {repo} (ref: main).",
                    "paper_urls": paper_urls,
                    "expected_title": expected_title,
                    "monitor_url": f"https://github.com/{repo}/actions/workflows/{WORKFLOW_FILE}",
                }
            return {
                "success": False,
                "status_code": status_code,
                "error": f"Unexpected response code: {status_code}",
            }
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        return {"success": False, "status_code": e.code, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to trigger GitHub Actions: {e}"}


def tool_fetch_verified_markdown(paper_id_or_url: str) -> Dict[str, Any]:
    """Fetch verified markdown or ledger from local storage first, then GitHub branch 'data'."""
    target = paper_id_or_url.strip()
    target_clean = os.path.basename(target)
    default_data = "/app/data" if os.path.exists("/app") and os.access("/app", os.W_OK) else os.path.expanduser("~/.vpr/data")
    data_dir = os.environ.get("DATA_DIR", default_data)

    # 1. Local storage check (Free MCP / Docker mode)
    local_candidates = [
        os.path.join(data_dir, "markdown", target_clean),
        os.path.join(data_dir, "markdown", f"{target_clean}.md"),
        os.path.join(data_dir, target_clean),
        os.path.join("./papers", target_clean),
        os.path.join("./papers", f"{target_clean}.md"),
    ]
    for lp in local_candidates:
        if os.path.isfile(lp):
            try:
                with open(lp, "r", encoding="utf-8", errors="replace") as f:
                    return {
                        "success": True,
                        "source": "local_storage",
                        "path": lp,
                        "content": f.read(),
                    }
            except Exception as e:
                log(f"Error reading local file {lp}: {e}")

    # 2. Remote check via GitHub 'data' branch
    if target_clean in ("ledger.json", "extracted_papers.json"):
        remote_path = f"latest/{target_clean}"
    elif target_clean.endswith(".md"):
        remote_path = f"latest/markdown/{target_clean}"
    elif target_clean.isdigit():
        remote_path = f"latest/markdown/paper_{target_clean}.md"
    else:
        arxiv_match = re.search(r"(\d{4}\.\d{4,5})", target)
        if arxiv_match:
            ledger_url = f"{RAW_DATA_BASE_URL}/latest/extracted_papers.json"
            req = urllib.request.Request(ledger_url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    papers = json.loads(resp.read().decode("utf-8"))
                    for p in papers:
                        if arxiv_match.group(1) in p.get("url", "") or arxiv_match.group(1) in p.get("title", ""):
                            return {
                                "success": True,
                                "source": "github_data_branch",
                                "matched_paper": p.get("title"),
                                "url": p.get("url"),
                                "content_markdown": p.get("content_markdown"),
                                "markdown_file": p.get("markdown_file"),
                            }
            except Exception:
                pass
        remote_path = f"latest/markdown/{target_clean}.md"

    fetch_url = f"{RAW_DATA_BASE_URL}/{remote_path}"
    req = urllib.request.Request(fetch_url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            return {
                "success": True,
                "source": "github_data_branch",
                "source_url": fetch_url,
                "path": remote_path,
                "content": content,
            }
    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "status_code": e.code,
            "error": f"Not found at {fetch_url} (HTTP {e.code}).",
            "hint": "Check status or fetch ledger: vpr_fetch_verified_markdown('ledger.json')",
        }
    except Exception as e:
        return {"success": False, "error": f"Error fetching {fetch_url}: {e}"}


def run_local_pipeline(urls: List[str], expected_title: str = "") -> Dict[str, Any]:
    """Helper to crawl, validate, and convert papers locally to Markdown."""
    default_data = "/app/data" if os.path.exists("/app") and os.access("/app", os.W_OK) else os.path.expanduser("~/.vpr/data")
    data_dir = os.environ.get("DATA_DIR", default_data)
    md_dir = os.path.join(data_dir, "markdown")
    tmp_dir = os.path.join(data_dir, "temp")
    os.makedirs(md_dir, exist_ok=True)
    os.makedirs(tmp_dir, exist_ok=True)

    results: List[Dict[str, Any]] = []

    for idx, raw_url in enumerate(urls, 1):
        url = raw_url.strip()
        if not url:
            continue
        if re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", url):
            url = f"https://arxiv.org/pdf/{url}.pdf"
        elif "arxiv.org/abs/" in url:
            url = url.replace("arxiv.org/abs/", "arxiv.org/pdf/") + ".pdf"

        tmp_pdf = os.path.join(tmp_dir, f"crawl_{int(time.time())}_{idx}.pdf")
        md_file = f"paper_local_{idx}.md"
        md_path = os.path.join(md_dir, md_file)

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        download_ok = False
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                data = resp.read()
                if data[:4] == b"%PDF":
                    with open(tmp_pdf, "wb") as f:
                        f.write(data)
                    download_ok = True
        except Exception as e:
            results.append({
                "url": url,
                "status": "gagal_unduh",
                "reason": f"Download failed: {e}",
            })
            continue

        if not download_ok:
            results.append({
                "url": url,
                "status": "bukan_pdf",
                "reason": "Downloaded stream did not begin with %PDF header",
            })
            continue

        # Validate & Extract Text
        try:
            from pypdf import PdfReader
            reader = PdfReader(tmp_pdf)
            page_count = len(reader.pages)
            extracted_pages: List[str] = []
            full_text = ""

            for p_num, page in enumerate(reader.pages, 1):
                txt = page.extract_text() or ""
                full_text += f"\n{txt}"
                extracted_pages.append(f"## Page {p_num}\n\n{txt.strip()}\n")

            if len(full_text.strip()) < 2000:
                results.append({
                    "url": url,
                    "status": "tidak_terbaca",
                    "reason": "Text extracted < 2000 characters (scanned or protected)",
                })
                continue

            if expected_title:
                norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower())
                words = norm(expected_title).split()
                first_page = norm(reader.pages[0].extract_text() or "")
                hits = sum(1 for w in words if w in first_page)
                if words and (hits / len(words)) < 0.5:
                    results.append({
                        "url": url,
                        "status": "judul_tidak_cocok",
                        "reason": f"Title overlap < 50% for '{expected_title}'",
                    })
                    continue

            # Save clean markdown
            md_content = f"# Verified Paper {idx}\nSource: {url}\nPages: {page_count}\n\n" + "\n".join(extracted_pages)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            results.append({
                "url": url,
                "status": "valid",
                "pages": page_count,
                "markdown_file": md_file,
                "markdown_path": md_path,
                "preview": md_content[:500] + "...",
            })
        except Exception as e:
            results.append({
                "url": url,
                "status": "error_ekstraksi",
                "reason": str(e),
            })
        finally:
            # Zero binary retention: remove raw PDF
            if os.path.exists(tmp_pdf):
                try:
                    os.remove(tmp_pdf)
                except Exception:
                    pass

    return {
        "success": True,
        "mode": "free_mcp_local",
        "processed_count": len(results),
        "results": results,
    }


def tool_local_research(query: str, max_papers: int = 3) -> Dict[str, Any]:
    """
    Search and immediately crawl, validate, and convert papers locally.
    Enforces the 3x per 90s rate limiter.
    """
    limit_check = check_rate_limit()
    if limit_check:
        return limit_check

    search_res = tool_search_candidates(query, max_results=max_papers)
    candidates = search_res.get("candidates", [])
    if not candidates:
        return {
            "success": False,
            "error": search_res.get("error", "No candidate papers found for query"),
            "query": query,
        }

    urls = [c["pdf_url"] for c in candidates if c.get("pdf_url")]
    first_title = candidates[0].get("title", "") if candidates else ""
    pipeline_res = run_local_pipeline(urls, expected_title="")
    pipeline_res["query"] = query
    pipeline_res["candidates_searched"] = len(candidates)
    return pipeline_res


TOOLS = [
    {
        "name": "vpr_search_candidates",
        "description": "Search open-access academic papers via arXiv API. Enforces rate-limiting: max 3 calls per 90s.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic or keyword query (e.g. 'federated learning communication efficiency')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of candidate papers to retrieve (1-10, default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "vpr_trigger_sandbox",
        "description": "Trigger PDF verification & conversion. Free MCP Mode automatically runs local conversion when GITHUB_TOKEN is omitted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_urls": {
                    "type": "string",
                    "description": "Comma or newline-separated paper URLs or arXiv IDs (max 5 per execution)",
                },
                "expected_title": {
                    "type": "string",
                    "description": "Expected paper title to enforce anti-hallucination validation check (optional)",
                    "default": "",
                },
            },
            "required": ["paper_urls"],
        },
    },
    {
        "name": "vpr_fetch_verified_markdown",
        "description": "Fetch verified clean Markdown text or ledger status from local storage or GitHub 'data' branch.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "paper_id_or_url": {
                    "type": "string",
                    "description": "File identifier or name (e.g., '1', 'paper_1.md', 'ledger.json', or arXiv ID)",
                }
            },
            "required": ["paper_id_or_url"],
        },
    },
    {
        "name": "vpr_local_research",
        "description": "All-in-one local pipeline: search arXiv, download PDF, validate 4 stages, and convert to clean Markdown without requiring external tokens. Rate limited to 3x per 90s.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Research question or scientific topic to search and extract",
                },
                "max_papers": {
                    "type": "integer",
                    "description": "Number of top candidates to validate and convert (default: 3, max: 5)",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
]


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    msg_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS,
            },
        }

    if method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        args = params.get("arguments", {})

        if tool_name == "vpr_search_candidates":
            q = args.get("query", "")
            limit = args.get("max_results", 5)
            res = tool_search_candidates(q, limit)
        elif tool_name == "vpr_trigger_sandbox":
            urls = args.get("paper_urls", "")
            exp_title = args.get("expected_title", "")
            res = tool_trigger_sandbox(urls, exp_title)
        elif tool_name == "vpr_fetch_verified_markdown":
            target = args.get("paper_id_or_url", "")
            res = tool_fetch_verified_markdown(target)
        elif tool_name == "vpr_local_research":
            q = args.get("query", "")
            max_p = args.get("max_papers", 3)
            res = tool_local_research(q, max_p)
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method / tool '{tool_name}' not found",
                },
            }

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(res, indent=2, ensure_ascii=False),
                    }
                ]
            },
        }

    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {},
        }

    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Unhandled method: {method}",
            },
        }

    return None


def main() -> None:
    log(f"Starting {SERVER_NAME} v{SERVER_VERSION} (stdio JSON-RPC transport)...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            log(f"JSON decode error: {e}")
            continue

        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
