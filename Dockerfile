# syntax=docker/dockerfile:1
# Kali base: many bundled tools already present, and it's the platform this
# audience runs. The image installs one2one as a proper package (console
# entry point `one2one`), not the old `python3 one2one.py` flat script.
# Pin the base to the multi-arch manifest digest (rolling = daily updates; the
# digest pins this exact build for reproducible/attestable images). Re-pin with:
#   docker buildx imagetools inspect kalilinux/kali-rolling:latest
FROM kalilinux/kali-rolling:latest@sha256:3093a0bd1f1196f4b10ab8e4a671929a6cd0153768642e6aa20dfced5e4132c5

LABEL org.opencontainers.image.title="one2one" \
      org.opencontainers.image.description="All-in-One One2One for Security Researchers" \
      org.opencontainers.image.source="https://github.com/nareinnprs-create/one2one" \
      org.opencontainers.image.licenses="MIT"

# Runtime system deps: python + git (tools clone their own repos) + php/curl/wget
# (a handful of tools shell out to these). --no-install-recommends keeps it lean.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git python3 python3-pip python3-venv curl wget php && \
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

# Tools install their payloads at runtime under here; persist via a volume.
RUN mkdir -p /root/.one2one/tools
WORKDIR /root
ENTRYPOINT ["one2one"]
