#!/usr/bin/env python3
"""Render ledger.json -> kanban.html statis (stdlib saja)."""
import json, sys, html, os
from urllib.parse import urlparse

COLS = ["Backlog", "To Download", "Downloading", "Validating", "Valid", "Gagal", "Writing"]
MAP = {
    "backlog": "Backlog", "to_download": "To Download",
    "downloading": "Downloading", "validating": "Validating",
    "valid": "Valid", "writing": "Writing",
    "gagal_unduh": "Gagal", "bukan_pdf": "Gagal",
    "judul_tidak_cocok": "Gagal", "tidak_terbaca": "Gagal", "gagal": "Gagal",
}

def safe_href(u):
    """Izinkan hanya skema http:// dan https://; tolak skema berbahaya seperti javascript:"""
    if not u or not isinstance(u, str):
        return "#"
    val = u.strip()
    parsed = urlparse(val)
    if parsed.scheme.lower() in ("http", "https"):
        return val
    return "#"

def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "ledger.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "kanban.html"
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("items", data.get("papers", []))
    buckets = {c: [] for c in COLS}
    for e in items:
        buckets[MAP.get(str(e.get("status", "")).lower(), "Backlog")].append(e)
    cards = ""
    for col in COLS:
        cs = "".join(
            "<div class='c'><b>{}</b><br><small>{} | {}</small><br><a href='{}'>{}</a><br><i>{}</i><br><code>{}</code></div>".format(
                html.escape(str(x.get("title", "-"))),
                html.escape(str(x.get("authors", "-"))), html.escape(str(x.get("year", "-"))),
                html.escape(safe_href(x.get("url"))),
                html.escape((str(x.get("url")) if x.get("url") is not None else "-")[:60]),
                html.escape(str(x.get("reason", x.get("status", "")))),
                html.escape(str(x.get("local_file", ""))))
            for x in buckets[col]) or "<div class='empty'>-</div>"
        cards += "<div class='col'><h2>{} ({})</h2>{}</div>".format(col, len(buckets[col]), cs)
    css = ("body{font-family:sans-serif;margin:0;background:#f4f4f5}h1{padding:12px 16px;margin:0}"
        ".b{display:flex;gap:12px;padding:16px;overflow-x:auto}"
        ".col{background:#fff;border-radius:10px;min-width:260px;flex:1;padding:10px;box-shadow:0 1px 3px #0002}"
        ".c{border:1px solid #e4e4e7;border-radius:8px;padding:8px;margin:8px 0;font-size:14px}"
        ".empty{color:#999}.col h2{font-size:15px;margin:4px}")
    with open(dst, "w", encoding="utf-8") as f:
        f.write("<!doctype html><html><head><meta charset='utf-8'>"
            "<title>VPR Kanban</title><style>" + css + "</style></head>"
            "<body><h1>VPR Kanban</h1><div class='b'>" + cards + "</div></body></html>")
    print("wrote {} ({} cards)".format(dst, len(items)))

if __name__ == "__main__":
    main()
