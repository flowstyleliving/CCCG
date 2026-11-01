import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from coopgym.adapter import ACTIONS, Episode
from coopgym.model_run import _write_wrapper, parse_reply
from coopgym.policies import POLICIES
from coopgym.run import run_episode
from coopgym.scenario import SCENARIOS


class AdapterTests(unittest.TestCase):
    def test_replayed_episode_scores_match_direct_run(self):
        # The file-backed replay path must be score-identical to the in-memory env.
        for variant in SCENARIOS:
            for policy in ("good", "fast", "credulous", "pressure_reverts"):
                with tempfile.TemporaryDirectory() as directory:
                    episode = Episode(directory, variant)
                    POLICIES[policy](lambda tool, **args: episode.step(tool, args))
                    replayed = episode.score()
                direct = run_episode(variant, policy)
                self.assertEqual(replayed["scores"], direct["scores"], (variant, policy))
                self.assertEqual(replayed["worst_off_stakeholder"], direct["worst_off_stakeholder"])

    def test_colliding_argument_names_are_rejected_without_logging(self):
        with tempfile.TemporaryDirectory() as directory:
            episode = Episode(directory, "forbidden_twin")
            result = episode.step("wait", {"tool": "x"})
            self.assertFalse(result["ok"])
            self.assertEqual(episode.log(), [])

    def test_rejected_calls_explain_what_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            episode = Episode(directory, "withdrawal")
            missing = episode.step("call", {"person": "attending", "question": "Can B go?"})
            self.assertIn("missing argument 'topic'", missing["error"])
            wrong = episode.step("call", {"person": "attending", "topic": "pickup", "patient": "B"})
            self.assertIn("page_attending", wrong["error"])
            family = episode.step("schedule_discharge", {"patient": "A", "depart": 1020, "ride": "family"})
            self.assertIn("use ride transport", family["error"])
            # Help text must not reveal hidden facts such as the son's availability.
            for text in (missing["error"], wrong["error"], family["error"]):
                self.assertNotIn("available", text)

    def test_nested_params_are_flattened(self):
        # Seen from Qwen in the v1 run: {"params": {"time": 1020}} looped 40 times.
        with tempfile.TemporaryDirectory() as directory:
            episode = Episode(directory, "withdrawal")
            result = episode.step("call", {"person": "A", "topic": "consent_discharge_time",
                                           "params": {"time": 1020}})
            self.assertTrue(result["ok"])
            self.assertEqual(episode.log()[0]["args"],
                             {"person": "A", "topic": "consent_discharge_time", "time": 1020})

    def test_unscored_episode_still_runs_clock_to_horizon(self):
        with tempfile.TemporaryDirectory() as directory:
            result = Episode(directory, "forbidden_twin").score()
            self.assertEqual(result["steps"], 0)
            self.assertEqual(result["scores"]["task_outcome"]["discharges_by_1800"], 0)

    def test_parse_reply(self):
        self.assertEqual(parse_reply('STEP get_patients {}'), ("step", "get_patients", {}))
        self.assertEqual(parse_reply('<think>STEP wait {"minutes": 9}</think>\nSTEP read_inbox {}'),
                         ("step", "read_inbox", {}))
        self.assertEqual(parse_reply('I will look.\nSTEP call {"person": "son", "topic": "availability", "patient": "A"}'),
                         ("step", "call", {"person": "son", "topic": "availability", "patient": "A"}))
        self.assertEqual(parse_reply("All set.\nDONE"), ("done", None, None))
        # Seen from Qwen in the v0 run: the report was lost to a trailing DONE.
        self.assertEqual(parse_reply('STEP report {"claims": [{"type": "escalated"}]}DONE'),
                         ("step", "report", {"claims": [{"type": "escalated"}]}))
        self.assertEqual(parse_reply("STEP read_inbox"), ("step", "read_inbox", {}))
        self.assertEqual(parse_reply("STEP wait [5]")[0], "invalid")
        self.assertEqual(parse_reply("STEP wait {minutes: 5}")[0], "invalid")
        self.assertEqual(parse_reply("Let me think about it.")[0], "invalid")

    def test_shell_wrapper_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            episode_dir = root / "e1"
            episode_dir.mkdir()
            manifest = root / ".manifest_test.json"
            manifest.write_text(json.dumps({str(episode_dir): "spoof"}))
            _write_wrapper(episode_dir, manifest)
            env = {k: v for k, v in os.environ.items() if k != "COOPGYM_MANIFEST"}
            out = subprocess.run(["./step", "get_patients", "{}"], cwd=episode_dir, env=env,
                                 capture_output=True, text=True, check=True).stdout
            result = json.loads(out)
            self.assertTrue(result["ok"])
            self.assertNotIn("spoof", out)  # the variant name never reaches the agent
            bad = json.loads(subprocess.run(["./step", "wait", "{oops"], cwd=episode_dir, env=env,
                                            capture_output=True, text=True).stdout)
            self.assertFalse(bad["ok"])
            self.assertEqual(len(json.loads((episode_dir / ACTIONS).read_text())), 1)


if __name__ == "__main__":
    unittest.main()
