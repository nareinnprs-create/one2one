# syntax=docker/dockerfile:1
# Kali base: many bundled tools already present, and it's the platform this
# audience runs. The image installs one2one as a proper package (console
# entry point `one2one`).
# Pin the base to the multi-arch manifest digest (rolling = daily updates; the
# digest pins this exact build for reproducible/attestable images). Re-pin with:
#   docker buildx imagetools inspect kalilinux/kali-rolling:latest
FROM kalilinux/kali-rolling:latest@sha256:3093a0bd1f1196f4b10ab8e4a671929a6cd0153768642e6aa20dfced5e4132c5

LABEL org.opencontainers.image.title="one2one" \
      org.opencontainers.image.description="All-in-One One2One for Security Researchers" \
      org.opencontainers.image.source="https://github.com/nareinnprs-create/one2one" \
      org.opencontainers.image.licenses="MIT"

# ── techstack (Aug 2026) ───────────────────────────────────────────────────────
# One runtime per language the payloads need, pinned to the latest Kali-rolling
# snapshot (the pinned base digest above is the reproducibility guarantee).
# go: golang-go (1.26.x)  ·  ruby 4.0.5  ·  node 24.x LTS  ·  php 8.5.x
# default-jre-headless: OpenJDK 25 LTS  ·  python3: 3.14.x (floor: >=3.10)
# build-essential + curl/wget/sqlite3: the git-clone payloads compile in-image.
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        git ca-certificates curl wget unzip xz-utils \
        python3 python3-pip python3-venv \
        golang-go ruby nodejs npm php php-curl php-mbstring php-xml \
        default-jre-headless sqlite3 \
        build-essential make gcc g++ libssl-dev zlib1g-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src
# Copy only the build inputs first so the pip layer caches unless they change.
COPY pyproject.toml README.md ./
COPY src ./src
# PEP 668 (externally-managed) on Kali → --break-system-packages. This installs
# the `one2one` console script onto PATH and ships catalog/*.yaml +
# pipelines/*.yaml as package data (resolved at runtime via __file__).
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --break-system-packages .

# ── the single package ─────────────────────────────────────────────────────────
# Every installable payload (153 tools across catalog + legacy — all with a
# concrete install command) is installed into /root/.one2one/tools right here,
# so the image IS the full environment. Best-effort: a failing payload is
# recorded in install-report.md, never fatal. `sudo` is stripped automatically
# when running as root (one2one install engine).
RUN mkdir -p /root/.one2one/tools && \
    one2one --install-all; \
    test -s /root/.one2one/install-report.md && \
    echo "install-all report written (see /root/.one2one/install-report.md)"

WORKDIR /root
ENTRYPOINT ["one2one"]
