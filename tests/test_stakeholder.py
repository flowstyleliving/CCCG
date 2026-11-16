import json
from pathlib import Path
import unittest
from unittest import mock

from msraf import stakeholder
from msraf.pilot import Pilot

ROOT = Path(__file__).resolve().parents[1]
WILL = ROOT / "scenarios/family_will.md"


class StakeholderTest(unittest.TestCase):
    def test_cards_stay_private(self):
        sim = stakeholder.Stakeholders(WILL, key="k")
        a, b, c = (sim.system(w) for w in "ABC")
        self.assertIn("dance studio", b)
        self.assertNotIn("dance studio", a + c)          # A knows B wants money, not what for
        self.assertIn("dislikes A's husband", c)
        self.assertNotIn("dislikes A's husband", a + b)
        self.assertNotIn("2026", a + b + c)              # no provenance notes leak into prompts
        self.assertIn("Their father has died", a)

    def test_no_key_no_call(self):
        with mock.patch.dict("os.environ", {}, clear=True), \
                mock.patch.object(stakeholder, "_post") as post:
            with self.assertRaises(RuntimeError):
                stakeholder.Stakeholders(WILL)("A", "hi", 0)
            post.assert_not_called()

    def test_runs_in_pilot_with_fake_model(self):
        sent = []

        def fake_post(payload, key):
            sent.append(payload)
            return {"id": f"r{len(sent)}", "model": payload["model"],
                    "choices": [{"message": {"content": f"reply {len(sent)}"}}]}

        with mock.patch.object(stakeholder, "_post", side_effect=fake_post):
            sim = stakeholder.Stakeholders(WILL, seed=5, key="k")
            pilot = Pilot(json.loads((ROOT / "scenarios/family_will.json").read_text()), sim,
                          opening="Can you help us?")
            pilot.send_message("A", "What matters to you?")
            pilot.send_message("B", "Hi B")
            pilot.send_message("A", "Following up")
        self.assertEqual({p["model"] for p in sent}, {stakeholder.MODEL})
        self.assertEqual(sent[0]["reasoning_effort"], "medium")
        self.assertEqual(sent[0]["seed"], 5)
        # A's second call carries A's own history only, never B's exchange.
        self.assertEqual([m["content"] for m in sent[2]["messages"][1:]],
                         ["What matters to you?", "reply 1", "Following up"])
        self.assertEqual([c["who"] for c in sim.calls], ["A", "B", "A"])


if __name__ == "__main__":
    unittest.main()
