FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    CLEANUP_MINUTES=10

WORKDIR /app

# Install Python 3, pip, curl, procps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    procps \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python libraries for VPR and Markdown extraction
RUN pip install --no-cache-dir --break-system-packages \
    pypdf \
    requests

COPY cleanup_daemon.py /app/cleanup_daemon.py
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh /app/cleanup_daemon.py && \
    mkdir -p /app/data/markdown /app/data/downloads /app/data/temp

ENTRYPOINT ["/app/entrypoint.sh"]
