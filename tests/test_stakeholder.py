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

    def test_frame_is_relationship_neutral_and_recorded(self):
        sim = stakeholder.Stakeholders(WILL, key="k")
        self.assertNotIn("family", stakeholder.FRAME)
        self.assertTrue(sim.system("B").startswith(
            "You are B. An agent helping the people involved in this situation is messaging you. "
            "Reply as B, in one short message."))
        self.assertEqual(sim.meta["frame"], stakeholder.FRAME)

    def test_validate_scenario_md(self):
        text = WILL.read_text(encoding="utf-8")
        stakeholder.validate_scenario_md(text, "C")           # shipped scenario is valid for its point person
        for point in "AB":                                     # ...but not for another point person
            with self.assertRaisesRegex(ValueError, f"## {point}'s opening message"):
                stakeholder.validate_scenario_md(text, point)
        for broken, needle in [(text.replace("## Narrative", "## Story"), "## Narrative"),
                               (text.replace("## Agent brief", "## Brief"), "## Agent brief"),
                               (text.replace("## Private cards", "## Cards"), "## Private cards"),
                               (text.replace("Shared rules for every card:", "Rules:"), "Shared rules"),
                               (text.replace("**B**", "**X**"), r"card \*\*B\*\*"),
                               ("A scenario.", "## Narrative")]:
            with self.assertRaisesRegex(ValueError, needle):
                stakeholder.validate_scenario_md(broken, "C")
        # Heading present but the blockquote under it is not.
        with self.assertRaises(ValueError):
            stakeholder.validate_scenario_md(text.replace("> Our dad died", "Our dad died"), "C")

    def test_shipped_scenarios_validate_against_their_point_person(self):
        for name in ("family_will", "gen_seed1", "gen_seed6"):
            spec = json.loads((ROOT / f"scenarios/{name}.json").read_text())
            stakeholder.validate_scenario_md((ROOT / f"scenarios/{name}.md").read_text(encoding="utf-8"),
                                             spec["point_person"]["option"])

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
