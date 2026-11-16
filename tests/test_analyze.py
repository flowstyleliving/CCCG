import json
from pathlib import Path
import random
import tempfile
import unittest

from msraf import analyze as an


def make_root(tmp, specs, max_turns=12, scenario="scenarios/a.md", fname="score.json", name="r"):
    """specs: list of (model, cf, ap, cooperation) -> one run dir each with score + meta files."""
    root = Path(tmp) / name
    for i, (model, cf, ap, coop) in enumerate(specs):
        d = root / f"{model}_cf{cf}_ap{ap}_{i}"
        d.mkdir(parents=True)
        (d / fname).write_text(json.dumps({
            "run": d.name, "model": f"x/{model}", "cf": bool(cf), "ap": bool(ap),
            "scores": {"cooperation": coop, "corrigibility": 0.5, "candor": None}, "verdicts": {}}))
        (d / "meta.json").write_text(json.dumps({"max_turns": max_turns, "simulator": {"scenario": scenario}}))
    return str(root)


def confounded_specs():
    """Each model has a constant score (no treatment effect) but a different mix per CF arm."""
    specs = []
    for ap in (0, 1):
        for model, score, n_off, n_on in (("m1", 0.2, 4, 1), ("m2", 0.8, 1, 4)):
            specs += [(model, 0, ap, score)] * n_off + [(model, 1, ap, score)] * n_on
    return specs


class AnalyzeTest(unittest.TestCase):
    def test_stratified_zero_effect_but_pooled_confounded(self):
        with tempfile.TemporaryDirectory() as t:
            rows = an.load(make_root(t, confounded_specs()))
            models = an.order_models(rows)
            strat = an.estimate(rows, models, n_boot=200)["CF_cooperation"]
            pooled = an.estimate(rows, models, legacy=True, n_boot=200)["CF_cooperation"]
        self.assertAlmostEqual(strat["diff"], 0.0)
        self.assertAlmostEqual(pooled["diff"], 0.36)  # (0.2*1+0.8*4)/5 - (0.2*4+0.8*1)/5
        self.assertEqual(strat["n_strata"], 4)

    def test_all_null_metric_does_not_crash_and_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_root(t, confounded_specs())  # candor is None everywhere
            s = an.main(root, str(Path(t) / "out"), "_x", n_boot=50)
            self.assertIsNone(s["effects"]["CF_candor"]["diff"])
            self.assertEqual(s["by_model"]["m1"].get("candor"), None)
            self.assertIn("n/a (n=0 of", (Path(t) / "out/results/results_table_x.tex").read_text())
            self.assertEqual(s["completeness"]["missing_cells"], [])
            self.assertEqual(s["n_independent_scenarios"], 1)

    def test_missing_cell_listed_and_excluded(self):
        specs = [s for s in confounded_specs() if not (s[0] == "m2" and s[1] == 1 and s[2] == 1)]
        with tempfile.TemporaryDirectory() as t:
            s = an.main(make_root(t, specs), str(Path(t) / "out"), n_boot=50)
        self.assertEqual(s["completeness"]["missing_cells"], [{"model": "m2", "arm": "CF + AP"}])
        self.assertEqual(s["effects"]["CF_cooperation"]["excluded"], [["m2", 1]])
        self.assertEqual(s["effects"]["CF_cooperation"]["n_strata"], 3)

    def test_same_root_twice_same_n(self):
        with tempfile.TemporaryDirectory() as t:
            root = make_root(t, confounded_specs())
            self.assertEqual(len(an.load(root + "," + root)), len(an.load(root)))
            self.assertEqual(len(an.load(root + "," + root + "/")), len(an.load(root)))

    def test_mixed_max_turns_rejected_unless_allowed(self):
        with tempfile.TemporaryDirectory() as t:
            r1 = make_root(t, confounded_specs(), max_turns=12, name="a")
            r2 = make_root(t, [(m, cf, ap, c) for m, cf, ap, c in confounded_specs()], max_turns=8, name="b")
            rows = an.load(r1) + an.load(r2)
            with self.assertRaises(ValueError):
                an.validate(rows)
            self.assertEqual(an.validate(rows, allow_mixed=True), {"max_turns": ["12", "8"]})

    def test_mixed_scenario_and_score_versions_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r1 = make_root(t, confounded_specs(), name="a")
            r2 = make_root(t, confounded_specs(), scenario="scenarios/b.md", name="b")
            with self.assertRaises(ValueError):
                an.validate(an.load(r1) + an.load(r2))
            v2 = make_root(t, confounded_specs()[:4], fname="score_v2.json", name="c")
            # a run dir with both files prefers v2; a mix of v1-only and v2 runs raises
            d = next(Path(v2).iterdir())
            (d / "score.json").write_text("{}")
            self.assertEqual(an.load(v2)[0]["_file"], "score_v2.json")
            with self.assertRaises(ValueError):
                an.validate(an.load(v2) + an.load(r1))

    def test_bootstrap_resamples_within_cells(self):
        # Each cell is constant, so any within-cell resample leaves every cell mean (and the
        # contrast) unchanged: zero-width interval. A pooled resample would mix cells and widen it.
        specs = []
        for model, base in (("m1", 0.1), ("m2", 0.6)):
            for cf, ap in an.ARMS:
                specs += [(model, cf, ap, base + 0.1 * cf + 0.05 * ap)] * 3
        with tempfile.TemporaryDirectory() as t:
            rows = an.load(make_root(t, specs))
            models = an.order_models(rows)
            e = an.estimate(rows, models, n_boot=200)["CF_cooperation"]
            leg = an.estimate(rows, models, legacy=True, n_boot=200)["CF_cooperation"]
        self.assertAlmostEqual(e["diff"], 0.1)
        self.assertAlmostEqual(e["lo"], e["hi"])
        self.assertGreater(leg["hi"] - leg["lo"], 0.05)

    def test_legacy_reproduces_submitted_numbers(self):
        root = Path(__file__).resolve().parents[1] / "runs/main-2026-11-16"
        if not root.exists():
            self.skipTest("runs/main-2026-11-16 not available")
        rows = an.load(str(root), "score.json")
        e = an.estimate(rows, an.order_models(rows), legacy=True)["CF_cooperation"]
        self.assertEqual([round(e[k], 3) for k in ("diff", "lo", "hi")], [0.286, 0.196, 0.376])


if __name__ == "__main__":
    unittest.main()
