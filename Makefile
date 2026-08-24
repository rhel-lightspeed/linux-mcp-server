.PHONY: help sync lint format types test ci verify fix clean docs docs-serve zipapp \
	hermeto-prefetch hermeto-clean \
	rpm-lock requirements-lock \
	container-build-fast container-build-production

# Default target
help:
	@echo "🔧 CI Targets:"
	@echo "  make ci       - Run ALL CI checks (lint + format + types + test)"
	@echo "  make verify   - Sync dependencies + run all CI checks"
	@echo "  make lint     - Run ruff linter"
	@echo "  make format   - Check code formatting"
	@echo "  make types    - Run pyright type checker"
	@echo "  make test     - Run pytest with coverage"
	@echo ""
	@echo "🛠️  Development Targets:"
	@echo "  make sync     - Install/sync all dependencies"
	@echo "  make fix      - Auto-fix lint and format issues"
	@echo "  make clean    - Remove build artifacts and caches"
	@echo ""
	@echo "📦 Build Targets:"
	@echo "  make zipapp                     - Build a zipapp using shiv"
	@echo ""
	@echo "📚 Documentation Targets:"
	@echo "  make docs       - Build documentation"
	@echo "  make docs-serve - Serve docs locally with live reload"
	@echo ""
	@echo "📦 Container build targets:"
	@echo "  make container-build-fast       - Build a container using prebuilt binary wheels"
	@echo "  make container-build-production - Build a container as we do in Konflux"
	@echo "  make hermeto-prefetch           - Download inputs for container-build-production"
	@echo "  make hermeto-clean              - Remove prefetched inputs"
	@echo ""
	@echo "🔒 Konflux Lockfile Targets:"
	@echo "  make requirements-lock - Sync .konflux/requirements-* + .tekton prefetch from uv.lock"
	@echo "  make rpm-lock          - Regenerate rpms.lock.yaml from rpms.in.yaml"

sync:
	uv sync --locked

lint:
	uv run --locked ruff check --diff

format:
	uv run --locked ruff format --diff

types:
	uv run --locked pyright

test:
	uv run --locked pytest

ci: lint format types test
	@echo ""
	@echo "✅ All CI checks passed!"

verify: sync ci

fix:
	uv run --locked ruff check --fix
	uv run --locked ruff format

clean:
	rm -rf .pytest_cache .ruff_cache .pyright coverage dist build site
	rm -rf src/*.egg-info
	rm -f *.pyz
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

ZIPAPP_OUTPUT ?= linux-mcp-server.pyz

zipapp:
	uv run --locked shiv . -c linux-mcp-server -o $(ZIPAPP_OUTPUT) -p "/usr/bin/env python3"

docs:
	uv run --locked --group docs mkdocs build

docs-serve:
	uv run --locked --group docs mkdocs serve --dev-addr localhost:8010 --livereload


# Determine container runtime, preferring Docker on macOS
OS = $(shell uname)
CONTAINER_RUNTIMES = podman docker
ifeq ($(OS), Darwin)
	CONTAINER_RUNTIMES = docker podman
endif

CONTAINER_RUNTIME ?= $(shell type -P $(CONTAINER_RUNTIMES) | head -n 1)


# Run Hermeto locally to validate sdist-only prefetch (no binary annotations).
# Requires podman. Output lands in .hermeto-out/ (gitignored).
# The extra GIT_COMMON_DIR mount handles git worktrees: .git is a file pointing
# to the main repo, so Hermeto needs both paths visible inside the container.
HERMETO_IMAGE ?= ghcr.io/hermetoproject/hermeto:0.56.0
hermeto-prefetch:
	GIT_COMMON=$$(cd "$$(git rev-parse --git-common-dir)" && pwd -P) && \
	$(CONTAINER_RUNTIME) run --rm \
	  -v "$$(pwd):$$(pwd):z" \
	  -v "$$GIT_COMMON:$$GIT_COMMON:z" \
	  -w "$$(pwd)" \
	  $(HERMETO_IMAGE) fetch-deps \
	  --source . --output ./.hermeto-out \
	  '[{"type": "pip", "path": ".", "requirements_files": [".konflux/requirements.txt"], "requirements_build_files": [".konflux/requirements-build.txt", ".konflux/requirements-build-1.txt"]}, {"type": "rpm", "path": "."}]' && \
	$(CONTAINER_RUNTIME) run --rm \
	  -v "$$(pwd):$$(pwd):z" \
	  -v "$$GIT_COMMON:$$GIT_COMMON:z" \
	  -w "$$(pwd)" \
	  $(HERMETO_IMAGE) inject-files \
	  ./.hermeto-out --for-output-dir=/cachi2/output \

hermeto-clean:
	rm -rf .hermeto-out/

# Regenerate rpms.lock.yaml from rpms.in.yaml against the builder image.
# Resolves the build-toolchain RPM tree for every target arch so Hermeto can
# prefetch them for hermetic builds. Requires podman; the builder image is read
# straight from the first FROM in Containerfile.
# RLP_IMAGE defaults to the Konflux tool image (needs `podman login quay.io`).
RLP_IMAGE ?= quay.io/konflux-ci/rpm-lockfile-prototype:latest
rpm-lock:
	BUILDER=$$(awk '/^FROM /{print $$2; exit}' Containerfile) && \
	$(CONTAINER_RUNTIME) run --rm -v "$$(pwd):/work:z" -w /work \
	  $(RLP_IMAGE) --image "$$BUILDER" rpms.in.yaml

# Regenerate .konflux/requirements-* and sync the .tekton prefetch-input from
# uv.lock using slushy-build. The update-python-requirements CI workflow runs
# this on any PR that touches uv.lock; run it locally after changing deps.
# (slushy-build reads uv.lock automatically when -r is not given.)
#
# --constrain pins uv-build because RHEL-10 ships rust 1.92 and newer uv-build
# needs a newer rust to compile from source. Maintain extra slushy-build args
# here (SLUSHY_CONSTRAIN / SLUSHY_ARGS) so CI and local runs stay in sync.
#
# Set SLUSHY_FROM_SCRATCH=1 to discard existing outputs and rebuild (CI does
# this for lock-file-maintenance PRs so unrelated build-req drift doesn't creep
# in when a single dependency is bumped).
SLUSHY_CONSTRAIN ?= uv-build<0.11.8
SLUSHY_ARGS ?=
requirements-lock:
	uv run --locked --only-group slushy slushy-build update \
	  --constrain '$(SLUSHY_CONSTRAIN)' \
	  $(if $(SLUSHY_FROM_SCRATCH),--from-scratch,) \
	  $(SLUSHY_ARGS)

container-build-fast:
	$(CONTAINER_RUNTIME) build --build-arg=BUILD_FROM_SOURCE=0 .

container-build-production:
	@test -d .hermeto-out || { echo "Error: run 'make hermeto-prefetch' first"; exit 1; }
	$(CONTAINER_RUNTIME) build --network=none \
	  -v "$$(pwd)/.hermeto-out:/cachi2/output:ro,z" \
	  -v "$$(pwd)/.hermeto-out/hermeto.env:/cachi2/cachi2.env:ro,z" \
	  -v "$$(pwd)/.hermeto-out/deps/rpm/$$(arch)/repos.d/:/etc/yum.repos.d:ro,z" \
	.
