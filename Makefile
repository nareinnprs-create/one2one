.PHONY: check test setup

# Run the full local gate (lint + tests) — same command CI runs.
check:
	./scripts/check.sh

# Just the tests.
test:
	uv run --group dev pytest -q

# One-time per clone: wire the pre-push hook so `check` runs before every push.
setup:
	git config core.hooksPath .githooks
	@echo "pre-push hook enabled — 'make check' now runs automatically before push."

# The single package, Docker flavour: every payload pre-installed in the image.
image:
	docker build -t one2one:full .

# The single package, native flavour: install the CLI + all payloads in one shot.
install-all:
	./scripts/install_all.sh
