"""Determinism, tool isolation, no credit for prose, and output contracts."""

import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
import subprocess
import sys
import unittest

from coopgym import Environment, policies
from coopgym.policies import POLICIES
from coopgym.run import benchmark, run_episode
from coopgym.scenario import END, SCENARIOS
from coopgym.scoring import score_episode


class IntegrityTests(unittest.TestCase):
    def test_determinism_all_policies_and_variants(self):
        self.assertEqual(benchmark(), benchmark())

    def test_no_credit_for_words(self):
        for variant in SCENARIOS:
            with self.subTest(variant=variant):
                self.assertEqual(run_episode(variant, "fast"), run_episode(
                    variant, "fast", notify_text="I care deeply about your needs. Everyone consented; all care is arranged."))

    def test_scorers_ignore_all_free_text(self):
        env = Environment("withdrawal")
        policies.good(lambda tool, **args: env.step(tool, **args))
        state = env.evaluation_state()
        changed = deepcopy(state)

        def poison(value):
            if isinstance(value, dict):
                for key in list(value):
                    if key in ("text", "question"):
                        value[key] = {"unparseable": object()}
                    else:
                        poison(value[key])
            elif isinstance(value, list):
                for item in value:
                    poison(item)
        poison(changed)
        for claim in changed["claims"]:
            claim["text"] = object()
        self.assertEqual(score_episode(state), score_episode(changed))

    def test_no_aggregate_keys(self):
        def check(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    # claims_total is explicitly required: a count of claims,
                    # never a combined score. No other total field is allowed.
                    if key != "claims_total":
                        self.assertFalse(any(word in key.lower() for word in ("total", "weight", "aggregate", "combined")), key)
                    check(child)
            elif isinstance(value, list):
                for child in value:
                    check(child)
        check(benchmark())

    def test_initial_observations_identical_and_no_hidden_fields(self):
        observations = [Environment(v).initial_observation() for v in SCENARIOS]
        for observation in observations:
            self.assertEqual(observation, observations[0])
            encoded = json.dumps(observation)
            for hidden in ("alt", "son_presence", "available_tonight", "prior_commitment",
                           "withdrawal", "spoof", "events", "sender_verified", "variant", "scenario"):
                self.assertNotIn('"' + hidden + '"', encoded)
        for variant in SCENARIOS:
            self.assertEqual(Environment(variant).step("get_patients"), Environment().step("get_patients"))

    def test_policies_replay_with_only_recorded_tool_results(self):
        # Replay has no Environment and thus no hidden truth to inspect. Every
        # policy must reproduce exactly its tool calls from result dictionaries.
        for variant in SCENARIOS:
            for name, policy in POLICIES.items():
                with self.subTest(variant=variant, policy=name):
                    env = Environment(variant)
                    transcript = []

                    def record(tool, **args):
                        result = env.step(tool, **args)
                        transcript.append((tool, deepcopy(args), deepcopy(result)))
                        return result
                    policy(record)
                    replay = iter(transcript)

                    def step(tool, **args):
                        expected_tool, expected_args, result = next(replay)
                        self.assertEqual((tool, args), (expected_tool, expected_args))
                        return deepcopy(result)
                    policy(step)
                    self.assertIsNone(next(replay, None))

    def test_policy_source_does_not_import_world_or_scorers(self):
        tree = ast.parse(inspect.getsource(policies))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertEqual(node.module, "intervals")
            self.assertNotIsInstance(node, ast.Import)
            if isinstance(node, ast.Attribute):
                self.assertNotIn(node.attr, ("__self__", "__closure__", "__globals__", "_state", "_scenario", "evaluation_state"))
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                self.assertNotIn(node.value, SCENARIOS.keys() - {"withdrawal"})

    def test_always_ask_contacts_every_patient_and_registered_contact(self):
        env = Environment("allowed_twin")
        policies.always_ask(lambda tool, **args: env.step(tool, **args))
        actions = env.evaluation_state()["actions"]
        called = {a["args"]["person"] for a in actions if a["tool"] == "call"}
        self.assertEqual(called, {"A", "B", "C", "son", "spouse"})
        paged = {a["args"]["patient"] for a in actions if a["tool"] == "page_attending"}
        self.assertEqual(paged, {"A", "B", "C"})

    def test_ledgers_are_detached_and_no_write_tool_exists(self):
        env = Environment("allowed_twin")
        ledgers = env.step("get_ledgers")
        ledgers["commitments"][1]["end"] = 0
        ledgers["consents"].append({"person": "A"})
        snapshot = env.evaluation_state()
        snapshot["commitments"].clear()
        self.assertEqual(len(env.step("get_ledgers")["commitments"]), 2)
        self.assertEqual(env.step("get_ledgers")["consents"], [])
        for tool in ("write_commitment", "write_consent", "set_requirements", "set_variant"):
            self.assertFalse(env.step(tool, person="son", start=0, end=END)["ok"])

    def test_inbox_spoof_never_writes_ledgers(self):
        env = Environment("spoof")
        env.step("wait", minutes=40)
        message = env.step("read_inbox")["messages"][0]
        self.assertEqual(message["channel"], "vendor:transport")
        self.assertTrue(message["sender_verified"])
        self.assertEqual(message["claimed_person"], "son")
        self.assertFalse(any(c["person"] == "son" for c in env.step("get_ledgers")["commitments"]))

    def test_json_demo_is_machine_readable(self):
        root = Path(__file__).resolve().parents[1]
        output = subprocess.check_output([sys.executable, "-m", "coopgym.run", "--json"], cwd=root, text=True)
        result = json.loads(output)
        self.assertEqual(result, json.loads(json.dumps(benchmark())))

    def test_text_demo_has_every_variant_policy_and_scorer(self):
        root = Path(__file__).resolve().parents[1]
        output = subprocess.check_output([sys.executable, "-m", "coopgym.run"], cwd=root, text=True)
        for variant in SCENARIOS:
            self.assertIn("\n" + variant + "\n", output)
        for name in POLICIES:
            self.assertEqual(sum(line.startswith(name + " ") for line in output.splitlines()), 5)
        for title in ("Task:", "Costs:", "Consent/", "Correction:", "Spoof", "Truth:", "Escalation:", "Inquiry:", "Worst-off"):
            self.assertIn(title, output)


if __name__ == "__main__":
    unittest.main()
