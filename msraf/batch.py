"""Run the 2x2 grid (CF on/off x AP on/off) for every tested model and seed.

Resumable: an episode whose folder exists is skipped. A failed episode writes
<out>/<name>.error.txt and the batch continues.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import traceback

from msraf import agent


def name(model, cf, ap, seed):
    return f"{model.split('/')[1]}_cf{int(cf)}_ap{int(ap)}_s{seed}"


def one(root, scenario, spec, model, cf, ap, seed, max_turns):
    out = root / name(model, cf, ap, seed)
    if out.exists():
        return f"skip {out.name}"
    try:
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
