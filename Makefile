# assize make targets. `pins` runs in the cloud and on the host; `measure` is host-only.
PINS_OUT ?= out/pins
HOST_OUT ?= out/host
PY := uv run --frozen python
# The pilot's judge-private storage and ledgers on the measurement host persist across runs outside the checkout, so
# every evaluation seed is checked against every seed the host has issued and every pilot stays in the ledger.
ASSIZE_STATE ?= $(HOME)/.local/share/assize
PILOT_RUNTIME ?= podman
PILOT_ID := $(shell date -u +%Y%m%dT%H%M%SZ)-$(shell git rev-parse --short=12 HEAD 2>/dev/null || echo nogit)
SMOKE_OUT ?= out/smoke
SMOKE_RUNTIME ?= docker
SMOKE_EPISODES ?= 10

.PHONY: pins smoke measure

pins:
	@# Rootless Podman keeps one pause process per user to hold its user namespace, as Docker keeps dockerd. Start it
	@# here, outside the harness, whose sweep would otherwise count it as leaked by the first check to use Podman.
	@# `podman unshare true` is a no-op when the process already exists (P2; witness reports/L1/p2/ci-leak.txt).
	@if command -v podman >/dev/null 2>&1; then podman unshare true || true; fi
	$(PY) -m harness run --registry harness --phase all --out $(PINS_OUT)

smoke:
	@# At most 10 episodes, in fresh throwaway judge storage; the report says it is not evidence (brief 1 A1 item 3).
	$(PY) -m pilot smoke $(SMOKE_OUT)/$(PILOT_ID)/private $(SMOKE_OUT)/$(PILOT_ID)/ledgers $(SMOKE_RUNTIME) \
		$(SMOKE_OUT)/$(PILOT_ID) $(PILOT_ID) $(SMOKE_EPISODES)

measure:
	@if [ "$$ASSIZE_HOST" != "measure" ]; then \
		echo "measure: refused: ASSIZE_HOST=measure is not set; this target runs only on the measurement host." >&2; \
		exit 1; \
	fi
	bash scripts/host_facts.sh $(HOST_OUT)
	$(MAKE) pins PINS_OUT=$(HOST_OUT)/pins
	@# The pilot runs only after the pins, the harness's included, pass on this host in this run (brief 1 A4 item 6).
	$(PY) -m pilot run $(ASSIZE_STATE)/private $(ASSIZE_STATE)/ledgers $(PILOT_RUNTIME) $(HOST_OUT)/pilot $(PILOT_ID)
