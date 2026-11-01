#!/usr/bin/env python3
"""
VPR Auto-Cleanup Daemon:
Runs periodically in the background inside the Docker container.
Deletes temporary PDF binary files older than CLEANUP_MINUTES (default: 10 minutes)
to prevent disk exhaustion, while preserving clean Markdown summaries and ledger records.
"""

import os
import sys
import time

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
CLEANUP_MINUTES = int(os.environ.get("CLEANUP_MINUTES", "10"))
MAX_AGE_SECONDS = CLEANUP_MINUTES * 60
CHECK_INTERVAL_SECONDS = 60


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [VPR-Cleanup] {msg}", flush=True)


def cleanup_old_files():
    now = time.time()
    deleted_count = 0
    freed_bytes = 0

    target_dirs = [
        os.path.join(DATA_DIR, "downloads"),
        os.path.join(DATA_DIR, "temp"),
        os.path.join(DATA_DIR, "_temp_pdf"),
    ]

    for d in target_dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in files:
                filepath = os.path.join(root, f)
                try:
                    mtime = os.path.getmtime(filepath)
                    age = now - mtime
                    # Delete PDFs and temp binary files older than limit
                    if age > MAX_AGE_SECONDS or f.endswith((".pdf", ".tmp", ".part")):
                        size = os.path.getsize(filepath)
                        os.remove(filepath)
                        deleted_count += 1
                        freed_bytes += size
                        log(f"Purged: {filepath} ({size} bytes, age: {int(age)}s)")
                except Exception as e:
                    log(f"Error purging {filepath}: {e}")

    if deleted_count > 0:
        log(f"Cleanup cycle done: {deleted_count} files removed, {freed_bytes / 1024:.2f} KB freed.")


def main():
    log(f"Started auto-cleanup daemon. Target: {DATA_DIR}, Threshold: {CLEANUP_MINUTES} minutes.")
    while True:
        try:
            cleanup_old_files()
        except Exception as e:
            log(f"Unexpected error in cycle: {e}")
        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
