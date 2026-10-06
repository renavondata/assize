# assize make targets. `pins` runs in the cloud and on the host; `measure` is host-only.
PINS_OUT ?= out/pins
HOST_OUT ?= out/host
PY := uv run --frozen python

.PHONY: pins smoke measure

pins:
	@# Rootless Podman keeps one pause process per user to hold its user namespace, as Docker keeps dockerd. Start it
	@# here, outside the harness, whose sweep would otherwise count it as leaked by the first check to use Podman.
	@# `podman unshare true` is a no-op when the process already exists (P2; witness reports/L1/p2/ci-leak.txt).
	@if command -v podman >/dev/null 2>&1; then podman unshare true || true; fi
	$(PY) -m harness run --registry harness --phase all --out $(PINS_OUT)

smoke:
	@echo "smoke: no-op placeholder at L0 (no Worlds yet)."

measure:
	@if [ "$$ASSIZE_HOST" != "measure" ]; then \
		echo "measure: refused: ASSIZE_HOST=measure is not set; this target runs only on the measurement host." >&2; \
		exit 1; \
	fi
	bash scripts/host_facts.sh $(HOST_OUT)
	$(MAKE) pins PINS_OUT=$(HOST_OUT)/pins
