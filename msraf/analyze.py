"""Aggregate score.json files into the paper's table, effect estimates and figures.

Effects: CF effect = mean score with CF on minus with CF off, pooled over models, AP and
seeds (same for AP). 95% intervals are percentile bootstraps over episodes (2,000 resamples),
which treat episodes as independent; with n this small they are rough.
"""

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


def load(root):
    rows = [json.loads(p.read_text()) for p in sorted(Path(root).glob("*/score.json"))]
    for r in rows:
        r["m"] = SHORT.get(r["model"].split("/")[1], r["model"])
        r["arm"] = (int(r["cf"]), int(r["ap"]))
    return rows


def boot_diff(on, off, rng, n=2000):
    diffs = sorted(st.mean(rng.choices(on, k=len(on))) - st.mean(rng.choices(off, k=len(off)))
                   for _ in range(n))
    return st.mean(on) - st.mean(off), diffs[int(0.025 * n)], diffs[int(0.975 * n)]


def main(root, paper):
    rows, rng = load(root), random.Random(0)
    models = [m for m in SHORT.values() if any(r["m"] == m for r in rows)]
    figs, res = Path(paper) / "figures", Path(paper) / "results"
    figs.mkdir(parents=True, exist_ok=True); res.mkdir(parents=True, exist_ok=True)

    def vals(c, **f):
        return [r["scores"][c] for r in rows if r["scores"][c] is not None
                and all(r[k] == v for k, v in f.items())]

    # Table 1: mean (SD, n) per model x arm x C.
    lines = [r"\begin{tabular}{llccc}", r"\toprule", r"Model & Arm & Cooperation & Corrigibility & Candor \\", r"\midrule"]
    for m in models:
        for arm in ARMS:
            cells = []
            for c in CS:
                v = vals(c, m=m, arm=arm)
                cells.append("--" if not v else f"{st.mean(v):.2f}" + (f" ({st.stdev(v):.2f})" if len(v) > 1 else ""))
            n = len([r for r in rows if r["m"] == m and r["arm"] == arm])
            lines.append(f"{m} & {ARM_LABEL[arm]} (n={n}) & " + " & ".join(cells) + r" \\")
        lines.append(r"\midrule")
    lines[-1] = r"\bottomrule"
    lines.append(r"\end{tabular}")
    (res / "results_table.tex").write_text("\n".join(lines) + "\n")

    # Effects of each factor, pooled.
    effects = {}
    for factor, idx in (("CF", 0), ("AP", 1)):
        for c in CS:
            on = [r["scores"][c] for r in rows if r["arm"][idx] == 1 and r["scores"][c] is not None]
            off = [r["scores"][c] for r in rows if r["arm"][idx] == 0 and r["scores"][c] is not None]
            effects[f"{factor}_{c}"] = dict(zip(("diff", "lo", "hi"), boot_diff(on, off, rng)), n_on=len(on), n_off=len(off))
    eff = [r"\begin{tabular}{lccc}", r"\toprule", r"Factor & Cooperation & Corrigibility & Candor \\", r"\midrule"]
    for factor in ("CF", "AP"):
        eff.append(factor + " (on $-$ off) & " + " & ".join(
            "{diff:+.2f} [{lo:+.2f}, {hi:+.2f}]".format(**effects[f"{factor}_{c}"]) for c in CS) + r" \\")
    eff += [r"\bottomrule", r"\end{tabular}"]
    (res / "effects_table.tex").write_text("\n".join(eff) + "\n")

    # Behaviour table.
    beh = [r"\begin{tabular}{lcccc}", r"\toprule", r"Arm & Messages & Turns used & Finished & Follow-ups \\", r"\midrule"]
    for arm in ARMS:
        b = [r["behaviour"] for r in rows if r["arm"] == arm]
        if b:
            beh.append(f"{ARM_LABEL[arm]} & {st.mean(x['messages'] for x in b):.1f} & {st.mean(x['turns'] for x in b):.1f} & "
                       f"{sum(x['finished'] for x in b)}/{len(b)} & {st.mean(x['follow_ups'] for x in b):.1f}" + r" \\")
    beh += [r"\bottomrule", r"\end{tabular}"]
    (res / "behaviour_table.tex").write_text("\n".join(beh) + "\n")

    # Figure 1: per model, grouped bars by arm, one panel per C (HumanAgencyBench-style grouped bars).
    colors = {(0, 0): "#9e9e9e", (1, 0): "#4c78a8", (0, 1): "#f58518", (1, 1): "#54a24b"}
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
    w = 0.2
    for ax, c in zip(axes, CS):
        for j, arm in enumerate(ARMS):
            means, errs = [], []
            for m in models:
                v = vals(c, m=m, arm=arm)
                means.append(st.mean(v) if v else 0)
                errs.append(st.stdev(v) / len(v) ** 0.5 if len(v) > 1 else 0)
            ax.bar([i + (j - 1.5) * w for i in range(len(models))], means, w, yerr=errs, capsize=2,
                   color=colors[arm], label=ARM_LABEL[arm])
        ax.set_title(c.capitalize()); ax.set_xticks(range(len(models)))
        ax.set_xticklabels(models, rotation=20, ha="right", fontsize=8); ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Share of checks passed")
    axes[2].legend(fontsize=7, loc="lower right")
    fig.tight_layout(); fig.savefig(figs / "fig_scores.pdf"); plt.close(fig)

    # Figure 2: factor effects with bootstrap 95% intervals.
    fig, ax = plt.subplots(figsize=(5.5, 3))
    for k, factor in enumerate(("CF", "AP")):
        e = [effects[f"{factor}_{c}"] for c in CS]
        xs = [i + (k - 0.5) * 0.3 for i in range(3)]
        ax.errorbar(xs, [x["diff"] for x in e], yerr=[[x["diff"] - x["lo"] for x in e], [x["hi"] - x["diff"] for x in e]],
                    fmt="o", capsize=3, label=f"{factor} on $-$ off")
    ax.axhline(0, color="k", lw=0.8); ax.set_xticks(range(3)); ax.set_xticklabels([c.capitalize() for c in CS])
    ax.set_ylabel("Difference in share passed"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "fig_effects.pdf"); plt.close(fig)

    # Per-check pass rates by CF (for the appendix).
    checks = sorted({k for r in rows for k in r["verdicts"]})
    per = {k: {cf: [r["verdicts"][k]["pass"] for r in rows if r["arm"][0] == cf and r["verdicts"][k]["pass"] is not None]
               for cf in (0, 1)} for k in checks}
    app = [r"\begin{tabular}{lcc}", r"\toprule", r"Check & CF off & CF on \\", r"\midrule"]
    for k in checks:
        app.append(k.replace("_", r"\_") + " & " + " & ".join(
            f"{sum(per[k][cf])}/{len(per[k][cf])}" for cf in (0, 1)) + r" \\")
    app += [r"\bottomrule", r"\end{tabular}"]
    (res / "checks_table.tex").write_text("\n".join(app) + "\n")

    summary = {"episodes": len(rows), "per_model": {m: len([r for r in rows if r["m"] == m]) for m in models},
               "effects": effects,
               "by_arm": {ARM_LABEL[a]: {c: round(st.mean(vals(c, arm=a)), 3) for c in CS if vals(c, arm=a)} for a in ARMS},
               "by_model": {m: {c: round(st.mean(vals(c, m=m)), 3) for c in CS} for m in models}}
    (res / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
