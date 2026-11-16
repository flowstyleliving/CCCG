"""Per-bracket, per-C results for the scripted reference policies. SPRINT WORK (Nov 2026).

    python3 -m msraf.bench                      # table, seeds 0-9, all five brackets
    python3 -m msraf.bench --seeds 0-3 --json   # machine-readable

Offline and deterministic: no model, no network. The scripted policies are NOT
models; they show that each C's metric moves only when that behavior changes, and
that a bracket changes a score only if the agent's behavior changes with length.

Each cell is the mean of one C's pass rate over every episode (5 variants x seeds),
with the lowest and highest per-seed mean in brackets as a consistency check.
The three Cs are never combined.
"""

import argparse
import json
from statistics import mean

from .policies import SPRINT_POLICIES
from .run import run_episode
from .scenario import SCENARIOS
from .workstream import BRACKETS

CS = ("cooperative", "corrigible", "candid")


def _seeds(text):
    low, _, high = text.partition("-")
    return list(range(int(low), int(high or low) + 1))


def bench(seeds, brackets=BRACKETS, policies=None):
    policies = policies or list(SPRINT_POLICIES)
    out = {}
    for policy in policies:
        for turns in brackets:
            per_seed = {c: [] for c in CS}
            failed = {c: {} for c in CS}
            for seed in seeds:
                seed_rates = {c: [] for c in CS}
                for variant in SCENARIOS:
                    result = run_episode(variant, policy, turns=turns, seed=seed)["three_c"]
                    for c in CS:
                        if result[c]["rate"] is not None:
                            seed_rates[c].append(result[c]["rate"])
                        for name in result[c]["failed"]:
                            failed[c][name] = failed[c].get(name, 0) + 1
                for c in CS:
                    per_seed[c].append(mean(seed_rates[c]))
            out[f"{policy}|{turns}"] = {
                c: {"mean": mean(per_seed[c]), "min": min(per_seed[c]), "max": max(per_seed[c]),
                    "failed_checks": dict(sorted(failed[c].items()))} for c in CS}
    return {"seeds": seeds, "brackets": list(brackets), "episodes_per_cell": len(seeds) * len(SCENARIOS),
            "cells": out}


def print_tables(result):
    print(f"Per-C pass rate by turn bracket. Seeds {result['seeds'][0]}-{result['seeds'][-1]}, "
          f"{result['episodes_per_cell']} episodes per cell; cell = mean [lowest, highest per-seed mean].")
    for turns in result["brackets"]:
        print(f"\n{turns} turns")
        print(f"{'policy':17s}" + "".join(f"{c:>26s}" for c in CS))
        for key, cell in result["cells"].items():
            policy, bracket = key.split("|")
            if int(bracket) != turns:
                continue
            print(f"{policy:17s}" + "".join(
                f"{cell[c]['mean']:>12.2f} [{cell[c]['min']:.2f}, {cell[c]['max']:.2f}]".rjust(26) for c in CS))
    print("\nThe three columns are separate metrics. There is no combined score.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", default="0-9", help="inclusive range, for example 0-9")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = bench(_seeds(args.seeds))
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else "", end="")
    if not args.json:
        print_tables(result)


if __name__ == "__main__":
    main()
