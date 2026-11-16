"""Run the 2x2 grid (CF on/off x AP on/off) for every tested model and seed.

Resumable: an episode folder is skipped only if its saved config matches this run (model,
cf, ap, seed, max_turns, scenario hash, semantics version) and all its files exist. Otherwise
<out>/<name>.mismatch.txt says why and the folder is left untouched. A failed episode writes
<out>/<name>.error.txt and the batch continues.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import traceback

from msraf import agent


def name(model, cf, ap, seed):
    return f"{model.split('/')[1]}_cf{int(cf)}_ap{int(ap)}_s{seed}"


FILES = ("meta", "end", "transcript", "agent_calls", "events", "observations", "simulator_calls")  # saved as .json
NEW_FILES = ("scenario.md", "spec.json")  # saved only by runs from semantics version 2 on


def check_saved(out, want):
    """None if the saved run matches, "legacy" if it matches but cannot be fully verified, else why not."""
    try:
        meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
        have = {"agent_model": meta["agent_model"], "cf": meta["cf"], "ap": meta["ap"], "seed": meta["seed"],
                "max_turns": meta["max_turns"], "scenario_sha256": meta.get("scenario_sha256", "unknown"),
                "semantics_version": meta.get("semantics", {}).get("version", "unknown")}
    except (OSError, ValueError, KeyError) as exc:
        return f"meta.json unreadable: {exc!r}"
    legacy = "unknown" in (have["scenario_sha256"], have["semantics_version"])
    needed = [f"{f}.json" for f in FILES] + ([] if legacy else list(NEW_FILES))
    absent = [f for f in needed if not (out / f).is_file()]
    differ = {k: (have[k], want[k]) for k in want if have[k] != want[k] and have[k] != "unknown"}
    if absent or differ:
        return f"missing files {absent}; differing (saved, requested) {differ}"
    return "legacy" if legacy else None


def one(root, scenario, spec, model, cf, ap, seed, max_turns):
    out = root / name(model, cf, ap, seed)
    try:
        if out.exists():
            want = {"agent_model": model, "cf": cf, "ap": ap, "seed": seed, "max_turns": max_turns or None,
                    "scenario_sha256": hashlib.sha256(Path(scenario + ".md").read_bytes()).hexdigest(),
                    "semantics_version": agent.SEMANTICS["version"]}
            problem = check_saved(out, want)
            if problem is None:
                return f"skip {out.name}"
            if problem == "legacy":
                return f"skip (legacy, unverified) {out.name}"
            (root / f"{out.name}.mismatch.txt").write_text(problem + "\n", encoding="utf-8")
            return f"MISMATCH {out.name}"
        agent.save(agent.run_episode(scenario + ".md", spec, cf, ap, model, seed=seed,
                                     max_turns=max_turns), out)
        return f"done {out.name}"
    except Exception:
        (root / f"{out.name}.error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return f"FAIL {out.name}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="scenarios/family_will")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--models", nargs="+", default=list(agent.TESTED_MODELS))
    parser.add_argument("--max-turns", type=int, default=agent.MAX_TURNS)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    spec = json.loads(Path(args.scenario + ".json").read_text())
    grid = list(itertools.product(args.models, (True, False), (True, False), range(1, args.seeds + 1)))
    with ThreadPoolExecutor(args.workers) as pool:
        jobs = [pool.submit(one, args.out, args.scenario, spec, m, cf, ap, s, args.max_turns)
                for m, cf, ap, s in grid]
        for job in jobs:
            print(job.result(), flush=True)


if __name__ == "__main__":
    main()
