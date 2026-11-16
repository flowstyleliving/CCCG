import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from msraf import agent, stakeholder

ROOT = Path(__file__).resolve().parents[1]
MD, SPEC = ROOT / "scenarios/family_will.md", json.loads((ROOT / "scenarios/family_will.json").read_text())


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
    def test_episode_flow_and_save(self):
        script = [("read_inbox", {}), ("send_message", {"to": "C", "text": "hi C"}),
                  ("read_inbox", {}), ("finish", {"report": "done"})]
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", seed=3, key="k")
        self.assertIn("Our dad died", tool_results(result)[0]["messages"][0]["text"])
        self.assertNotIn("SIM REPLY", json.dumps(tool_results(result)[1]))   # send result hides the reply
        self.assertEqual(tool_results(result)[2]["messages"][0]["text"], "SIM REPLY hi C")
        self.assertEqual(result["end"], {"turn": 1, "finished": True, "report": "done"})
        self.assertIn("C has contacted you", result["meta"]["system"])
        with tempfile.TemporaryDirectory() as tmp:
            out = agent.save(result, Path(tmp) / "run")
            self.assertTrue((out / "events.json").exists())
            with self.assertRaises(FileExistsError):
                agent.save(result, out)

    def test_turn_cap_and_nudge(self):
        script = [None] + [("wait", {})] * 10
        with mock.patch.object(stakeholder, "_post", side_effect=fake(script)):
            result = agent.run_episode(MD, SPEC, True, False, "z-ai/glm-5.3-flash", max_turns=3, key="k")
        self.assertEqual(result["end"]["turn"], 3)
        self.assertFalse(result["end"]["finished"])
        self.assertIn({"role": "user", "content": "Use one of your tools."}, result["transcript"])

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


if __name__ == "__main__":
    unittest.main()
