# assize make targets. `pins` runs in the cloud and on the host; `measure` is host-only.
PINS_OUT ?= out/pins
# Empty by default, so `make pins` runs every pin. The `pins` workflow passes `--since <sha> --since-run <id>` from
# `python -m harness base` to run only the pins witnessing a path changed since that green head (instruction #108).
PINS_SINCE ?=
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

.PHONY: pins smoke measure nethack366-image

# The NetHack 3.6.6 game image (worlds/nethack366/image) is built before the pins run, outside any pin's time limit: a
# cold build compiles NLE and takes longer than a pin may. The build is cached by the runtime and tagged by the recipe's
# hash. A failed build is not fatal here: pin P40 then fails on its own, for the one reason.
nethack366-image:
	-$(PY) -c "from worlds.nethack366 import binding; print(binding.build())"

pins: nethack366-image
	$(PY) -m harness run --registry harness --phase all --out $(PINS_OUT) $(PINS_SINCE)

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
