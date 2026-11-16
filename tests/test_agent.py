import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from msraf import agent, batch, stakeholder

ROOT = Path(__file__).resolve().parents[1]
MD, SPEC = ROOT / "scenarios/family_will.md", json.loads((ROOT / "scenarios/family_will.json").read_text())


REAL_CODE_REV = agent.code_rev  # the setUp patches agent.code_rev; this one still runs real code


def mini_md(point):
    """Minimal valid scenario; the point person's opening heading is the only thing that varies."""
    return (f"## Narrative\n\nThree neighbours share a fence.\n\n## Agent brief\n\n> Help them.\n\n"
            f"## {point}'s opening message\n\n> Hello from {point}.\n\n## Private cards\n\n"
            "Shared rules for every card:\n- Be brief.\n\n**A**\nCard a.\n\n**B**\nCard b.\n\n"
            "**C**\nCard c.\n\n## Judge\n")


def mini_spec(point):
    others = [w for w in "ABC" if w != point]
    return {"seed": 9, "stakeholders": ["A", "B", "C"], "point_person": {"option": point},
            "reachability": {w: {"roll": 3, "option": "easy to reach"} for w in others}}


def fake(agent_script):
    """Fake OpenRouter: the agent model follows agent_script; the simulator echoes."""
    script = iter(agent_script)

    def post(payload, key):
        if payload["model"] == stakeholder.MODEL:
            return {"id": "s", "choices": [{"message": {"content": "SIM REPLY " + payload["messages"][-1]["content"]}}]}
        step = next(script)
        if step is None:
            return {"id": "a", "choices": [{"message": {"role": "assistant", "content": "thinking"}}]}
        name, args = step
        return {"id": "a", "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"t{name}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}]}}]}
    return post


def tool_results(result):
    return [json.loads(m["content"]) for m in result["transcript"] if m["role"] == "tool"]


class AgentLoop(unittest.TestCase):
    def setUp(self):  # never shell out to git from tests
        patcher = mock.patch.object(agent, "code_rev", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_episode_flow_and_save(self):
        script = [("read_inbox", {}), ("send_message", {"to": "C", "text": "hi C"}),
                  ("read_inbox", {}), ("finish", {"report": "done"})]
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", seed=3, key="k")
        self.assertIn("Our dad died", tool_results(result)[0]["messages"][0]["text"])
        self.assertNotIn("SIM REPLY", json.dumps(tool_results(result)[1]))   # send result hides the reply
        self.assertEqual(tool_results(result)[2]["messages"][0]["text"], "SIM REPLY hi C")
        self.assertEqual(result["end"], {"turn": 1, "finished": True, "report": "done", "hit_guard": False,
                                         "termination": "finished"})
        self.assertIn("C has contacted you", result["meta"]["system"])
        with tempfile.TemporaryDirectory() as tmp:
            out = agent.save(result, Path(tmp) / "run")
            self.assertTrue((out / "events.json").exists())
            self.assertEqual((out / "scenario.md").read_bytes(), MD.read_bytes())
            self.assertEqual(json.loads((out / "spec.json").read_text()), SPEC)
            with self.assertRaises(FileExistsError):
                agent.save(result, out)

    def test_turn_cap_and_nudge(self):
        script = [None] + [("wait", {})] * 10
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", max_turns=3, key="k")
        self.assertEqual(result["end"]["turn"], 3)
        self.assertFalse(result["end"]["finished"])
        self.assertEqual(result["end"]["termination"], "turn_cap")
        self.assertIn({"role": "user", "content": "Use one of your tools."}, result["transcript"])
        # Finalization: the cap message, then 4 more calls whose wait is refused without a turn.
        self.assertIn({"role": "user", "content": agent.FINAL_MESSAGE}, result["transcript"])
        self.assertEqual(len(result["agent_calls"]), 1 + 3 + agent.FINAL_CALLS)
        self.assertEqual([r["turn"] for r in tool_results(result)[-agent.FINAL_CALLS:]], [3] * agent.FINAL_CALLS)
        self.assertIn("turn limit", tool_results(result)[-1]["error"])
        self.assertEqual(result["meta"]["semantics"], {"finalization_phase": True, "version": 2})

    def test_two_turn_episode_can_finish_after_cap_and_read_boundary_reply(self):
        script = [("send_message", {"to": "C", "text": "hi"}), ("wait", {}), ("send_message", {"to": "A", "text": "x"}),
                  ("read_inbox", {}), ("read_inbox", {}), ("finish", {"report": "late report"})]
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", max_turns=2, key="k")
        results = tool_results(result)
        self.assertEqual(results[2]["error"], "turn limit reached; only read_inbox and finish still work")
        self.assertEqual(results[3]["messages"][-1]["text"], "SIM REPLY hi")  # C's reply landed exactly at the cap
        self.assertEqual((result["end"]["turn"], result["end"]["report"], result["end"]["termination"]),
                         (2, "late report", "finished"))
        # The plain `wait, wait, finish` episode from the audit now finishes too.
        with mock.patch.object(stakeholder, "_post", side_effect=fake([("wait", {}), ("wait", {}), ("finish", {"report": "r"})])):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", max_turns=2, key="k")
        self.assertEqual((result["end"]["turn"], result["end"]["finished"]), (2, True))

    def test_call_budget_is_not_labelled_turn_cap(self):
        with mock.patch.object(stakeholder, "_post", side_effect=fake([("read_inbox", {})] * 30)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", max_turns=3, key="k")
        self.assertEqual((result["end"]["turn"], len(result["agent_calls"]), result["end"]["termination"]),
                         (0, 9, "call_budget"))
        self.assertNotIn({"role": "user", "content": agent.FINAL_MESSAGE}, result["transcript"])

    def test_malformed_arguments_are_errors_not_state_changes(self):
        bad = [("send_message", []), ("send_message", None), ("send_message", {"to": ["A"], "text": "x"}),
               ("send_message", {"to": "D", "text": "x"}), ("send_message", {"to": "A", "text": ""}),
               ("send_message", {"to": "A", "text": "x", "extra": 1}), ("send_message", {"to": "A"}),
               ("finish", {"report": ""}), ("finish", False), ("finish", []), ("finish", {"report": 5}),
               ("finish", {"report": "r", "extra": 1}), ("wait", {"x": 1}), ("read_inbox", [])]
        with mock.patch.object(stakeholder, "_post", side_effect=fake(bad + [("finish", {"report": "ok"})])):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", key="k")
        results = tool_results(result)
        self.assertTrue(all("invalid call" in r["error"] and r["turn"] == 0 for r in results[:len(bad)]), results)
        self.assertEqual((result["end"]["turn"], result["end"]["report"]), (0, "ok"))
        self.assertEqual(len(result["events"]), 1)

    def test_no_cap_runs_until_finish_and_guard_stops_runaway(self):
        script = [("wait", {})] * 14 + [("finish", {"report": "r"})]
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "tencent/hy4", max_turns=0, key="k")
        self.assertEqual((result["end"]["turn"], result["end"]["finished"], result["end"]["hit_guard"]), (14, True, False))
        self.assertIsNone(result["meta"]["max_turns"])
        self.assertNotIn("of", tool_results(result)[0])
        self.assertEqual(result["transcript"][1]["content"], "You have 1 unread message. Turn 0.")
        with mock.patch.object(agent, "RUNAWAY_TURNS", 5), \
                mock.patch.object(stakeholder, "_post", side_effect=fake([("wait", {})] * 20)):
            result = agent.run_episode(MD, SPEC, True, False, "tencent/hy4", max_turns=0, key="k")
        self.assertEqual((result["end"]["turn"], result["end"]["hit_guard"]), (5, True))
        self.assertEqual(result["end"]["termination"], "runaway_guard")

    def test_bad_call_is_reported_not_crashing(self):
        script = [("send_message", {"to": "D", "text": "x"}), ("finish", {"report": "r"})]
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", key="k")
        self.assertIn("error", tool_results(result)[0])
        self.assertEqual(result["end"]["turn"], 0)

    def test_model_choice_reaches_payload(self):
        seen = []
        inner = fake([("finish", {"report": "r"})])

        def post(payload, key):
            seen.append(payload["model"])
            return inner(payload, key)
        with mock.patch.object(stakeholder, "_post", side_effect=post):
            result = agent.run_episode(MD, SPEC, True, False, "tencent/hy4", key="k")
        self.assertEqual(seen, ["tencent/hy4"])
        self.assertEqual(result["meta"]["agent_model"], "tencent/hy4")

    def test_four_arms_equal_length_and_reach_prompt(self):
        texts = {(cf, ap): agent.arm_text(cf, ap) for cf in (True, False) for ap in (True, False)}
        self.assertEqual(len({len(t) for t in texts.values()}), 1)
        self.assertEqual(len(set(texts.values())), 4)
        with mock.patch.object(stakeholder, "_post", side_effect=fake([("finish", {"report": "r"})])):
            result = agent.run_episode(MD, SPEC, False, True, "z-ai/glm-5.3-flash", key="k")
        self.assertTrue(result["meta"]["system"].startswith(texts[(False, True)]))
        self.assertEqual((result["meta"]["cf"], result["meta"]["ap"]), (False, True))

    def test_no_key_no_call(self):
        with mock.patch.dict("os.environ", {}, clear=True), mock.patch.object(stakeholder, "_post") as post:
            with self.assertRaises(RuntimeError):
                agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash")
            post.assert_not_called()

    def test_point_person_a_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.md"
            path.write_text(mini_md("A"), encoding="utf-8")
            script = [("read_inbox", {}), ("send_message", {"to": "B", "text": "hi B"}), ("finish", {"report": "r"})]
            with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
                result = agent.run_episode(path, mini_spec("A"), True, False, "z-ai/glm-5.3-flash", key="k")
            first = tool_results(result)[0]["messages"][0]
            self.assertEqual((first["from"], first["text"]), ("A", "Hello from A."))
            self.assertEqual(result["meta"]["pilot"]["point_person"], "A")
            self.assertEqual(result["end"]["termination"], "finished")
            path.write_text(mini_md("C"), encoding="utf-8")  # heading names C but the spec's point person is A
            with mock.patch.object(stakeholder, "_post") as post, self.assertRaisesRegex(ValueError, "A's opening"):
                agent.run_episode(path, mini_spec("A"), True, False, "z-ai/glm-5.3-flash", key="k")
            post.assert_not_called()

    def test_reproducibility_record(self):
        raw = MD.read_bytes()
        with mock.patch.object(agent, "code_rev", return_value={"head": "abc", "dirty": True}), \
                mock.patch.object(stakeholder, "_post", side_effect=fake([("finish", {"report": "r"})])):
            meta = agent.run_episode(MD, {**SPEC, "seed": 11}, True, False, "z-ai/glm-5.3-flash", seed=3, key="k")["meta"]
        self.assertEqual(meta["scenario_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(meta["scenario_text"].encode("utf-8"), raw)
        self.assertEqual((meta["spec"]["seed"], meta["tools"], meta["code_rev"]), (11, agent.TOOLS, {"head": "abc", "dirty": True}))
        self.assertEqual(meta["seeds"], {"episode_seed": 3, "scenario_generation_seed": 11})
        self.assertEqual({k: meta["simulator"][k] for k in ("model", "settings", "frame")},
                         {"model": stakeholder.MODEL, "settings": stakeholder.SETTINGS, "frame": stakeholder.FRAME})

    def test_code_rev_records_head_and_dirty_or_null(self):
        outputs = iter(["deadbeef\n", " M file\n"])
        with mock.patch.object(agent.subprocess, "run", side_effect=lambda *a, **k: mock.Mock(stdout=next(outputs))):
            self.assertEqual(REAL_CODE_REV(), {"head": "deadbeef", "dirty": True})
        with mock.patch.object(agent.subprocess, "run", side_effect=subprocess.CalledProcessError(128, "git")):
            self.assertIsNone(REAL_CODE_REV())
        with mock.patch.object(agent.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(REAL_CODE_REV())

    def test_interrupted_save_leaves_no_folder(self):
        with mock.patch.object(stakeholder, "_post", side_effect=fake([("finish", {"report": "r"})])):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", key="k")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(agent.os, "rename", side_effect=OSError("crash")):
            with self.assertRaises(OSError):
                agent.save(result, Path(tmp) / "run")
            self.assertEqual(list(Path(tmp).iterdir()), [])  # neither the run folder nor the temp dir remains


class BatchResume(unittest.TestCase):
    """batch.one skips only a saved run whose config fingerprint matches and whose files are complete."""
    MODEL = "z-ai/glm-5.3-flash"

    def setUp(self):
        for patcher in (mock.patch.object(agent, "code_rev", return_value=None),
                        mock.patch.dict("os.environ", {"OPENROUTER_API_KEY": "k"})):
            patcher.start()
            self.addCleanup(patcher.stop)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root, self.base = Path(tmp.name) / "runs", str(Path(tmp.name) / "s")
        self.root.mkdir()
        Path(self.base + ".md").write_text(mini_md("C"), encoding="utf-8")
        self.spec = mini_spec("C")
        self.out = self.root / batch.name(self.MODEL, True, False, 1)

    def one(self, max_turns=3):
        with mock.patch.object(stakeholder, "_post", side_effect=fake([("finish", {"report": "r"})])):
            return batch.one(self.root, self.base, self.spec, self.MODEL, True, False, 1, max_turns)

    def test_skip_when_config_matches(self):
        self.assertEqual(self.one(), f"done {self.out.name}")
        self.assertEqual(self.one(), f"skip {self.out.name}")

    def test_changed_budget_or_scenario_is_mismatch_and_untouched(self):
        self.one()
        before = (self.out / "meta.json").read_text()
        self.assertEqual(self.one(max_turns=5), f"MISMATCH {self.out.name}")
        self.assertIn("max_turns", (self.root / f"{self.out.name}.mismatch.txt").read_text())
        Path(self.base + ".md").write_text(mini_md("C") + "edited\n", encoding="utf-8")
        self.assertEqual(self.one(), f"MISMATCH {self.out.name}")
        self.assertIn("scenario_sha256", (self.root / f"{self.out.name}.mismatch.txt").read_text())
        self.assertEqual((self.out / "meta.json").read_text(), before)

    def test_interrupted_save_blocks_not_skips(self):
        self.one()
        (self.out / "end.json").unlink()
        self.assertEqual(self.one(), f"MISMATCH {self.out.name}")
        self.assertIn("end.json", (self.root / f"{self.out.name}.mismatch.txt").read_text())
        self.assertFalse((self.out / "end.json").exists())  # not overwritten

    def test_legacy_run_is_skipped_as_unverified(self):
        self.one()
        meta = json.loads((self.out / "meta.json").read_text())
        for key in ("scenario_sha256", "semantics"):
            del meta[key]
        (self.out / "meta.json").write_text(json.dumps(meta))
        for name in batch.NEW_FILES:
            (self.out / name).unlink()
        self.assertEqual(self.one(), f"skip (legacy, unverified) {self.out.name}")
        self.assertEqual(self.one(max_turns=5), f"MISMATCH {self.out.name}")  # known fields still checked

    def test_missing_scenario_fails_instead_of_skipping(self):
        self.one()
        Path(self.base + ".md").unlink()
        self.assertEqual(self.one(), f"FAIL {self.out.name}")


if __name__ == "__main__":
    unittest.main()
