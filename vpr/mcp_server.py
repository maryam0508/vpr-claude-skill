#!/usr/bin/env python3
"""
VPR MCP Server: Model Context Protocol (stdio transport) server for Claude / AI Assistants.
Provides 3 tools:
1. vpr_search_candidates(query, max_results): Search open-access papers via arXiv API.
2. vpr_trigger_sandbox(paper_urls, expected_title): Trigger GitHub Actions workflow dispatch on maryam0508/vpr-claude-skill.
3. vpr_fetch_verified_markdown(paper_id_or_url): Fetch verified markdown text from branch 'data' of the repository.
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

SERVER_NAME = "vpr-mcp-server"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

DEFAULT_REPO = "maryam0508/vpr-claude-skill"
WORKFLOW_FILE = "vpr-sandbox.yml"
RAW_DATA_BASE_URL = f"https://raw.githubusercontent.com/{DEFAULT_REPO}/data"

USER_AGENT = "VPR-MCPServer/1.0 (+https://github.com/maryam0508/vpr-claude-skill)"


def log(msg: str) -> None:
    sys.stderr.write(f"[vpr-mcp] {msg}\n")
    sys.stderr.flush()


def tool_search_candidates(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search arXiv API for academic papers matching the query."""
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
    """Trigger GitHub Actions workflow dispatch in maryam0508/vpr-claude-skill."""
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not github_token:
        return {
            "success": False,
            "error": "GITHUB_TOKEN / GH_TOKEN environment variable is not set. Token is required for workflow_dispatch.",
        }

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
    """Fetch verified markdown or ledger from GitHub branch 'data'."""
    target = paper_id_or_url.strip()
    target_clean = os.path.basename(target)

    # Determine filename
    if target_clean in ("ledger.json", "extracted_papers.json"):
        remote_path = f"latest/{target_clean}"
    elif target_clean.endswith(".md"):
        remote_path = f"latest/markdown/{target_clean}"
    elif target_clean.isdigit():
        remote_path = f"latest/markdown/paper_{target_clean}.md"
    else:
        # Check if arxiv ID or general paper identifier
        arxiv_match = re.search(r"(\d{4}\.\d{4,5})", target)
        if arxiv_match:
            # First fetch extracted_papers.json to find corresponding paper file
            ledger_url = f"{RAW_DATA_BASE_URL}/latest/extracted_papers.json"
            req = urllib.request.Request(ledger_url, headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    papers = json.loads(resp.read().decode("utf-8"))
                    for p in papers:
                        if arxiv_match.group(1) in p.get("url", "") or arxiv_match.group(1) in p.get("title", ""):
                            return {
                                "success": True,
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
                "source_url": fetch_url,
                "path": remote_path,
                "content": content,
            }
    except urllib.error.HTTPError as e:
        # Fallback: check if ledger exists
        return {
            "success": False,
            "status_code": e.code,
            "error": f"Not found at {fetch_url} (HTTP {e.code}). Note: run might still be processing or file name differs.",
            "hint": f"Check status or fetch ledger: vpr_fetch_verified_markdown('ledger.json')",
        }
    except Exception as e:
        return {"success": False, "error": f"Error fetching {fetch_url}: {e}"}


TOOLS = [
    {
        "name": "vpr_search_candidates",
        "description": "Search open-access academic papers via arXiv API to get candidates before verification.",
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
        "description": "Trigger GitHub Actions sandbox on maryam0508/vpr-claude-skill to download, 4-stage validate, and convert papers to clean Markdown.",
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
        "description": "Fetch verified clean Markdown text or ledger status from the repository 'data' branch.",
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
