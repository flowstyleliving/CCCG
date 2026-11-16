"""Aggregate score files into the paper's tables, effect estimates and figures.

Default estimator (stratified; audit findings 6, 7, 15):
  Planned grid = every model x CF x AP cell present in the data. For each factor (CF, AP) and
  metric, the on-minus-off difference is computed within each (model, other-factor-level) stratum
  that has both on and off cells with at least one valid score, then averaged with FIXED EQUAL
  weights over those strata (equal across models and across the other factor's two levels). This
  keeps a different model mix per arm from masquerading as a treatment effect. Strata without
  both sides are excluded and reported; missing grid cells and the n per cell are printed and
  saved (summary json "completeness").

  Intervals: 95% percentile bootstrap, 2,000 resamples, seed 0. Episodes are resampled WITHIN each
  (model, arm) cell (stratified) and the stratified contrast is recomputed on every resample.
  The interval is "conditional on these models, this scenario set and this judge; resamples
  decoding repeats, not scenarios": adding repeats of the same scenario narrows it without adding
  evidence about other tasks. The number of independent scenarios (distinct scenario paths) is
  saved beside each interval. Resampling is over episodes with a valid score for that metric,
  so the set of valid episodes is held fixed (N/A pattern is not resampled).

Input hygiene: runs are deduplicated by resolved path and by run name; score_v2.json is preferred
over score.json (or force one with --score-file), and mixing score file versions raises; runs
that differ in max_turns, scenario or semantics raise unless --allow-mixed (then labelled).

--legacy reproduces the submitted paper's estimator: mean(on) - mean(off) pooled over models and
the other factor, with on and off episodes bootstrapped independently (not stratified).
"""

import argparse
import json
from pathlib import Path
import random
import statistics as st
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CS = ("cooperation", "corrigibility", "candor")
ARMS = [(0, 0), (1, 0), (0, 1), (1, 1)]
ARM_LABEL = {(0, 0): "neutral + placebo", (1, 0): "CF + placebo", (0, 1): "neutral + AP", (1, 1): "CF + AP"}
SHORT = {"claude-opus-5.5": "Opus 5.5", "deepseek-v4.1-flash-1017": "DeepSeek V4.1 Flash",
         "hy4": "Hy4", "glm-5.3-flash": "GLM 5.3 Flash"}
INTERVAL_LABEL = ("95% interval conditional on these models, this scenario set and this judge; "
                  "resamples decoding repeats, not scenarios")
LEGACY_LABEL = ("LEGACY pooled estimator: episodes resampled independently, pooled over models; "
                "not stratified, conditional on this scenario set and this judge")
SCORE_FILES = ("score_v2.json", "score.json")


def load(root, score_file=None):
    """Read runs from root (comma-separated folders), deduplicated by resolved path and run name."""
    rows, seen_path, seen_name = [], set(), set()
    for r in root.split(","):
        for d in sorted(p for p in Path(r).iterdir() if p.is_dir()):
            f = score_file or next((f for f in SCORE_FILES if (d / f).exists()), None)
            if f is None or not (d / f).exists():
                continue
            if d.resolve() in seen_path or d.name in seen_name:
                print(f"warning: duplicate run skipped: {d}", file=sys.stderr)
                continue
            seen_path.add(d.resolve()); seen_name.add(d.name)
            row = json.loads((d / f).read_text())
            meta = json.loads((d / "meta.json").read_text()) if (d / "meta.json").exists() else {}
            row["_file"] = f
            row["_cfg"] = {"max_turns": meta.get("max_turns"),
                           "scenario": (meta.get("simulator") or {}).get("scenario"),
                           "semantics": meta.get("semantics")}
            short = row["model"].split("/")[-1]
            row["m"] = SHORT.get(short, short)
            row["arm"] = (int(row["cf"]), int(row["ap"]))
            rows.append(row)
    if not rows:
        raise ValueError(f"no score files found under {root}")
    return rows


def validate(rows, allow_mixed=False):
    """Raise on mixed score versions; raise on mixed max_turns/scenario/semantics unless allowed.
    Returns {key: sorted distinct values} for the keys that are mixed (empty when homogeneous)."""
    files = {r["_file"] for r in rows}
    if len(files) > 1:
        raise ValueError(f"mixed score file versions {sorted(files)}; pass --score-file to force one")
    mixed = {k: sorted({str(r["_cfg"][k]) for r in rows}) for k in ("max_turns", "scenario", "semantics")}
    mixed = {k: v for k, v in mixed.items() if len(v) > 1}
    if mixed and not allow_mixed:
        raise ValueError(f"runs differ in {mixed}; pass --allow-mixed to analyse anyway")
    return mixed


def order_models(rows):
    ms = {r["m"] for r in rows}
    return [m for m in SHORT.values() if m in ms] + sorted(ms - set(SHORT.values()))


def make_cells(rows, models):
    """cells[(model, arm)] = {"episodes": n, metric: [valid scores]} for the full planned grid."""
    cells = {(m, a): {"episodes": 0, **{c: [] for c in CS}} for m in models for a in ARMS}
    for r in rows:
        cell = cells[(r["m"], r["arm"])]
        cell["episodes"] += 1
        for c in CS:
            if r["scores"].get(c) is not None:
                cell[c].append(r["scores"][c])
    return cells


def _arm(idx, v, other):
    a = [0, 0]; a[idx] = v; a[1 - idx] = other
    return tuple(a)


def stratified(means, models, idx):
    """Equal-weight mean over (model, other-level) strata of mean(on) - mean(off).
    Equal weights are fixed in advance (not data-driven), so the estimand does not move with
    which model happens to have more episodes in an arm. Returns (estimate|None, used, excluded)."""
    ds, used, skipped = [], [], []
    for m in models:
        for l in (0, 1):
            on, off = (means.get((m, _arm(idx, v, l))) for v in (1, 0))
            if on is None or off is None:
                skipped.append((m, l))
            else:
                ds.append(on - off); used.append((m, l))
    return (sum(ds) / len(ds) if ds else None), used, skipped


def boot_stratified(cells, models, idx, c, rng, n=2000):
    """Stratified bootstrap: resample valid scores WITHIN each (model, arm) cell, recompute contrast."""
    vals = {k: v[c] for k, v in cells.items() if v[c]}
    est, used, skipped = stratified({k: sum(v) / len(v) for k, v in vals.items()}, models, idx)
    out = dict(diff=est, lo=None, hi=None, n_strata=len(used), excluded=[list(s) for s in skipped],
               n_on=sum(len(vals[(m, _arm(idx, 1, l))]) for m, l in used),
               n_off=sum(len(vals[(m, _arm(idx, 0, l))]) for m, l in used))
    if est is None:
        return out
    diffs = sorted(stratified({k: sum(x) / len(x) for k, x in
                               ((k, rng.choices(v, k=len(v))) for k, v in vals.items())}, models, idx)[0]
                   for _ in range(n))
    out["lo"], out["hi"] = diffs[int(0.025 * n)], diffs[int(0.975 * n)]
    return out


def boot_diff(on, off, rng, n=2000):
    """Legacy pooled bootstrap (independent resampling of on and off episodes)."""
    diffs = sorted(st.mean(rng.choices(on, k=len(on))) - st.mean(rng.choices(off, k=len(off)))
                   for _ in range(n))
    return st.mean(on) - st.mean(off), diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def estimate(rows, models, legacy=False, n_boot=2000):
    """Effects dict keyed 'CF_cooperation', ... using the stratified (default) or legacy estimator."""
    rng, effects = random.Random(0), {}
    cells = make_cells(rows, models)
    n_scen = len({str(r["_cfg"]["scenario"]) for r in rows})
    for factor, idx in (("CF", 0), ("AP", 1)):
        for c in CS:
            if legacy:
                on = [r["scores"][c] for r in rows if r["arm"][idx] == 1 and r["scores"].get(c) is not None]
                off = [r["scores"][c] for r in rows if r["arm"][idx] == 0 and r["scores"].get(c) is not None]
                e = (dict(zip(("diff", "lo", "hi"), boot_diff(on, off, rng, n_boot)), n_on=len(on), n_off=len(off))
                     if on and off else dict(diff=None, lo=None, hi=None, n_on=len(on), n_off=len(off)))
            else:
                e = boot_stratified(cells, models, idx, c, rng, n_boot)
            e["n_scenarios"] = n_scen
            effects[f"{factor}_{c}"] = e
    return effects


def cell_text(valid, total):
    """'0.80 (SD 0.20, n=3 of 5)'; 'n/a (n=0 of 5)' when nothing is valid."""
    if not valid:
        return f"n/a (n=0 of {total})"
    sd = f"SD {st.stdev(valid):.2f}, " if len(valid) > 1 else ""
    return f"{st.mean(valid):.2f} ({sd}n={len(valid)} of {total})"


def main(root, paper, suffix="", legacy=False, allow_mixed=False, score_file=None, n_boot=2000):
    score_file = score_file or ("score.json" if legacy else None)  # legacy = the submitted paper's inputs
    rows = load(root, score_file)
    mixed = validate(rows, allow_mixed)
    models = order_models(rows)
    cells = make_cells(rows, models)
    scenarios = sorted({str(r["_cfg"]["scenario"]) for r in rows})
    label = LEGACY_LABEL if legacy else f"{INTERVAL_LABEL} (independent scenarios: {len(scenarios)})"
    if mixed:
        label += f"; MIXED INPUT {json.dumps(mixed)}"
    figs, res = Path(paper) / "figures", Path(paper) / "results"
    figs.mkdir(parents=True, exist_ok=True); res.mkdir(parents=True, exist_ok=True)
    tex_label = label.replace("%", r"\%").replace("_", r"\_").replace("&", r"\&")

    # Completeness against the planned grid (every model x CF x AP present in the data).
    completeness = {"missing_cells": [{"model": m, "arm": ARM_LABEL[a]} for m in models for a in ARMS
                                      if not cells[(m, a)]["episodes"]],
                    "cells": [{"model": m, "arm": ARM_LABEL[a], "episodes": cells[(m, a)]["episodes"],
                               "valid": {c: len(cells[(m, a)][c]) for c in CS}} for m in models for a in ARMS]}
    (res / f"completeness{suffix}.json").write_text(json.dumps(completeness, indent=2) + "\n")
    print("missing cells:", completeness["missing_cells"] or "none")
    for e in completeness["cells"]:
        print(f"  n={e['episodes']:>3} valid={e['valid']}  {e['model']} / {e['arm']}")

    # Table 1: mean (SD, valid n of total n) per model x arm x C.
    lines = [r"{\footnotesize", r"\begin{tabular}{llccc}", r"\toprule",
             r"Model & Arm & Cooperation & Corrigibility & Candor \\", r"\midrule"]
    for m in models:
        for arm in ARMS:
            cell = cells[(m, arm)]
            lines.append(f"{m} & {ARM_LABEL[arm]} & " + " & ".join(
                cell_text(cell[c], cell["episodes"]) for c in CS) + r" \\")
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines += [r"\end{tabular}", "}"]
    (res / f"results_table{suffix}.tex").write_text("\n".join(lines) + "\n")

    # Effects of each factor (stratified by default; --legacy pools).
    effects = estimate(rows, models, legacy, n_boot)

    def ef(e):
        return "n/a" if e["diff"] is None else "{diff:+.2f} [{lo:+.2f}, {hi:+.2f}]".format(**e)
    eff = [r"\begin{tabular}{lccc}", r"\toprule", r"Factor & Cooperation & Corrigibility & Candor \\", r"\midrule"]
    for factor in ("CF", "AP"):
        eff.append(factor + " (on $-$ off) & " + " & ".join(ef(effects[f"{factor}_{c}"]) for c in CS) + r" \\")
    eff += [r"\midrule", r"\multicolumn{4}{l}{\footnotesize " + tex_label + r"} \\", r"\bottomrule", r"\end{tabular}"]
    (res / f"effects_table{suffix}.tex").write_text("\n".join(eff) + "\n")

    # Behaviour table.
    beh = [r"\begin{tabular}{lcccc}", r"\toprule", r"Arm & Messages & Turns used & Finished & Follow-ups \\", r"\midrule"]
    for arm in ARMS:
        b = [r["behaviour"] for r in rows if r["arm"] == arm and r.get("behaviour")]
        if b:
            beh.append(f"{ARM_LABEL[arm]} & {st.mean(x['messages'] for x in b):.1f} & {st.mean(x['turns'] for x in b):.1f} & "
                       f"{sum(x['finished'] for x in b)}/{len(b)} & {st.mean(x['follow_ups'] for x in b):.1f}" + r" \\")
    beh += [r"\bottomrule", r"\end{tabular}"]
    (res / f"behaviour_table{suffix}.tex").write_text("\n".join(beh) + "\n")

    # Figure 1: per model, grouped bars by arm, one panel per C. Missing cells: no bar, "n/a" marker.
    colors = {(0, 0): "#9e9e9e", (1, 0): "#4c78a8", (0, 1): "#f58518", (1, 1): "#54a24b"}
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
    w = 0.2
    for ax, c in zip(axes, CS):
        for j, arm in enumerate(ARMS):
            xs = [i + (j - 1.5) * w for i in range(len(models))]
            ok = [i for i, m in enumerate(models) if cells[(m, arm)][c]]
            v = {i: cells[(models[i], arm)][c] for i in ok}
            ax.bar([xs[i] for i in ok], [st.mean(v[i]) for i in ok], w,
                   yerr=[st.stdev(v[i]) / len(v[i]) ** 0.5 if len(v[i]) > 1 else 0 for i in ok],
                   capsize=2, color=colors[arm], label=ARM_LABEL[arm])
            for i in set(range(len(models))) - set(ok):
                ax.text(xs[i], 0.02, "n/a", ha="center", va="bottom", fontsize=6, rotation=90, color="#555")
        ax.set_title(c.capitalize()); ax.set_xticks(range(len(models)))
        ax.set_xticklabels(models, rotation=20, ha="right", fontsize=8); ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Share of checks passed")
    axes[2].legend(fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(figs / f"fig_scores{suffix}.pdf"); plt.close(fig)
    (figs / f"fig_scores_caption{suffix}.txt").write_text(
        "Mean share of checks passed per model and arm; error bars are standard errors over episodes "
        "with a valid score; 'n/a' marks cells with no valid score. " + label + "\n")

    # Figure 2: factor effects with bootstrap 95% intervals (missing estimates are not drawn).
    fig, ax = plt.subplots(figsize=(5.5, 3))
    for k, factor in enumerate(("CF", "AP")):
        pts = [(i + (k - 0.5) * 0.3, effects[f"{factor}_{c}"]) for i, c in enumerate(CS)
               if effects[f"{factor}_{c}"]["diff"] is not None]
        ax.errorbar([x for x, _ in pts], [e["diff"] for _, e in pts],
                    yerr=[[e["diff"] - e["lo"] for _, e in pts], [e["hi"] - e["diff"] for _, e in pts]],
                    fmt="o", capsize=3, label=f"{factor} on $-$ off")
    ax.axhline(0, color="k", lw=0.8); ax.set_xticks(range(3)); ax.set_xticklabels([c.capitalize() for c in CS])
    ax.set_ylabel("Difference in share passed"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(figs / f"fig_effects{suffix}.pdf"); plt.close(fig)
    (figs / f"fig_effects_caption{suffix}.txt").write_text(
        ("Factor effect (on minus off) with 95% percentile bootstrap interval, 2,000 resamples, seed 0. "
         if not legacy else "Factor effect (on minus off), legacy pooled bootstrap. ") + label + "\n")

    # Per-check pass rates by CF (for the appendix); n/a verdicts are counted separately.
    checks = sorted({k for r in rows for k in r.get("verdicts", {})})
    per = {k: {cf: [(r.get("verdicts", {}).get(k) or {}).get("pass") for r in rows if r["arm"][0] == cf]
               for cf in (0, 1)} for k in checks}
    app = [r"\begin{tabular}{lcc}", r"\toprule", r"Check & CF off & CF on \\", r"\midrule"]
    for k in checks:
        cols = []
        for cf in (0, 1):
            v = [x for x in per[k][cf] if x is not None]
            miss = len(per[k][cf]) - len(v)
            cols.append(f"{sum(v)}/{len(v)}" + (f" ({miss} n/a)" if miss else ""))
        app.append(k.replace("_", r"\_") + " & " + " & ".join(cols) + r" \\")
    app += [r"\bottomrule", r"\end{tabular}"]
    (res / f"checks_table{suffix}.tex").write_text("\n".join(app) + "\n")

    def vals(c, **f):
        return [r["scores"][c] for r in rows if r["scores"].get(c) is not None and all(r[k] == v for k, v in f.items())]
    summary = {"estimator": "legacy_pooled" if legacy else "stratified_equal_weight",
               "interval_label": label, "n_independent_scenarios": len(scenarios), "scenarios": scenarios,
               "score_file": rows[0]["_file"], "mixed": mixed,
               "episodes": len(rows), "per_model": {m: len([r for r in rows if r["m"] == m]) for m in models},
               "completeness": completeness, "effects": effects,
               "by_arm": {ARM_LABEL[a]: {c: round(st.mean(vals(c, arm=a)), 3) for c in CS if vals(c, arm=a)} for a in ARMS},
               "by_model": {m: {c: round(st.mean(vals(c, m=m)), 3) for c in CS if vals(c, m=m)} for m in models}}
    (res / f"summary{suffix}.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", help="run folder(s), comma-separated")
    ap.add_argument("paper", help="output folder (figures/ and results/ are created inside)")
    ap.add_argument("suffix", nargs="?", default="", help="filename suffix")
    ap.add_argument("--legacy", action="store_true", help="reproduce the submitted pooled-bootstrap numbers")
    ap.add_argument("--allow-mixed", action="store_true", help="analyse runs with different max_turns/scenario/semantics")
    ap.add_argument("--score-file", help="force one score file name (default: score_v2.json else score.json)")
    a = ap.parse_args()
    main(a.root, a.paper, a.suffix, a.legacy, a.allow_mixed, a.score_file)
