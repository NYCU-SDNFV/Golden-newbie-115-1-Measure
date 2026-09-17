# Lab 2 -- Measurement + Datapath Tuning
# Do not modify this file. (protected; see .github/policy/manifest.sha256)
SHELL := /usr/bin/env bash
.SHELLFLAGS := -o pipefail -c

COMPOSE   ?= docker compose
CONTAINER ?= lab2
DEXEC      = docker exec $(CONTAINER)
IN         = /workspace

.PHONY: help build up down shell logs clean policy lab-test test test-offline \
        check-update update a1 a2 a3 a4 b1 b2 labels plot

help:
	@echo "make up        build the image and start the '$(CONTAINER)' container"
	@echo "make test      policy checks + all autograded checks (same as CI)"
	@echo "make check-update  check the required public starter version"
	@echo "make update    prepare a safe update branch, preserving your work"
	@echo "make test-offline  explicit local-only run without a freshness request"
	@echo "make a1        A1 baseline throughput / goodput / RTT        -> data/a1.{txt,json}"
	@echo "make a2        A2 BDP window sweep                           -> data/a2.{txt,json}"
	@echo "make a3        A3 offload on/off with CPU                    -> data/a3.{txt,json}"
	@echo "make a4        A4 latency under load, label 'bloat'          -> data/e5_bloat.*"
	@echo "make b1        B1 every label in harness/qdiscs.conf         -> data/e5_*.* + data/pareto.csv"
	@echo "make b2        B2 congestion control x loss, window control  -> data/b2.{txt,json}"
	@echo "make plot      CDF (figs/a4_cdf.png) and Pareto (figs/b1_pareto.png)"
	@echo "make shell     a shell inside the container"
	@echo "make clean     tear everything down (also cleans stale Mininet state)"

build:
	$(COMPOSE) build

# Socket-buffer ceilings live in the host kernel's root network namespace (see
# docker-compose.yml). Lift them through PID 1; harmless if already high enough.
CEILING = 67108864
up:
	$(COMPOSE) up -d --build
	@echo "waiting for $(CONTAINER) to be ready ..."
	@sh tests/wait_ready.sh
	@$(DEXEC) nsenter -t 1 -n -- sysctl -qw net.core.rmem_max=$(CEILING) net.core.wmem_max=$(CEILING) \
	   && echo "socket-buffer ceilings lifted to $(CEILING) bytes" \
	   || echo "warning: could not lift net.core.{r,w}mem_max (A2/B2 -w above ~200K will fail); on a Linux host: sudo sysctl -w net.core.rmem_max=$(CEILING) net.core.wmem_max=$(CEILING)"

down:
	-$(COMPOSE) down --remove-orphans

shell:
	$(DEXEC) -it bash 2>/dev/null || docker exec -it $(CONTAINER) bash

logs:
	-$(COMPOSE) ps
	-$(COMPOSE) logs --no-color --tail=200

clean:
	-$(DEXEC) mn -c >/dev/null 2>&1 || true
	-$(DEXEC) sh -c 'ip netns del nsA; ip netns del nsB; ip link del vethA' >/dev/null 2>&1 || true
	-$(COMPOSE) down -v --remove-orphans

# ---- exercises (all run inside the container) -------------------------------
a1:
	@mkdir -p data
	$(DEXEC) python3 $(IN)/harness/e1_baseline.py 2>&1 | tr -d '\r' | tee data/a1.txt

a2:
	@mkdir -p data
	$(DEXEC) python3 $(IN)/harness/e2_bdp.py 2>&1 | tr -d '\r' | tee data/a2.txt

a3:
	@mkdir -p data
	$(DEXEC) python3 $(IN)/harness/e4_offload.py 2>&1 | tr -d '\r' | tee data/a3.txt

a4:
	@mkdir -p data
	$(DEXEC) bash $(IN)/harness/e5_aqm.sh bloat 2>&1 | tr -d '\r' | tee data/a4.txt

# every non-comment label in harness/qdiscs.conf
labels:
	@awk '$$0 !~ /^[[:space:]]*#/ && NF >= 2 { print $$1 }' harness/qdiscs.conf

b1:
	@mkdir -p data
	@for l in $$($(MAKE) -s labels); do \
	   echo "=== label: $$l ==="; \
	   $(DEXEC) bash $(IN)/harness/e5_aqm.sh $$l 2>&1 | tr -d '\r' | tee data/b1_$$l.txt || exit 1; \
	 done
	$(DEXEC) python3 $(IN)/tools/collect_pareto.py

b2:
	@mkdir -p data
	$(DEXEC) python3 $(IN)/harness/e3_cc_loss.py 2>&1 | tr -d '\r' | tee data/b2.txt

plot:
	@mkdir -p figs
	$(DEXEC) sh -c 'cd $(IN) && python3 tools/plot_cdf.py data/e5_*.csv -o figs/a4_cdf.png'
	@test -f data/pareto.csv \
	  && $(DEXEC) sh -c 'cd $(IN) && python3 tools/plot_pareto.py data/pareto.csv -o figs/b1_pareto.png --slo-goodput 9 --slo-p99 20' \
	  || echo "(no data/pareto.csv yet -- run make b1 first)"

# ---- checks (what the autograder runs, in this order) ------------------------
policy:
	@bash .github/policy/00_layout.sh
	@bash .github/policy/01_integrity.sh

check-update:
	@python3 .github/release/upgrade.py check

update:
	@python3 .github/release/upgrade.py update

lab-test:
	@sh tests/00_env.sh
	@sh tests/10_a1.sh
	@sh tests/20_a2.sh
	@sh tests/30_a3.sh
	@sh tests/40_a4.sh
	@sh tests/50_b1.sh
	@sh tests/60_b2.sh
	@sh tests/70_report.sh
	@sh tests/80_git.sh
	@echo ""
	@echo "All checks passed."

test: check-update policy
	@$(MAKE) lab-test

test-offline: policy
	@echo "OFFLINE local run: remote release freshness is NOT checked."
	@echo "Official grading still enforces canonical protected files and release metadata."
	@$(MAKE) lab-test
