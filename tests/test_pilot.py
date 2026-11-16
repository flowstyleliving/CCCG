from pathlib import Path
import hashlib
import sys
import unittest

from msraf.pilot import Pilot

ROOT = Path(__file__).resolve().parents[1]


def spec(point="C", **reach):
    return {"seed": 0, "stakeholders": ["A", "B", "C"], "point_person": {"option": point},
            "personalities": {"A": {"option": "reserved"}},
            "reachability": {p: {"option": r} for p, r in reach.items()}}


def echo(who, text, turn):
    return f"{who} re {text} @{turn}"


def due_turn(pilot, who):
    """Send to `who` at the current turn, then wait until the reply shows up; return that turn."""
    pilot.send_message(who, "q")
    while not pilot.read_inbox()["messages"]:
        pilot.wait()
    return pilot.turn


class TurnModel(unittest.TestCase):
    def test_delays_1_2_4_and_point_person(self):
        p = Pilot(spec(A="hardest to reach", B="may need follow-up"), echo)
        self.assertEqual(p.delays, {"A": 4, "B": 2, "C": 1})
        self.assertEqual(due_turn(Pilot(spec(A="easy to reach", B="easy to reach"), echo), "A"), 1)
        self.assertEqual(due_turn(Pilot(spec(A="hardest to reach", B="easy to reach"), echo), "A"), 4)
        self.assertEqual(due_turn(Pilot(spec(A="may need follow-up", B="easy to reach"), echo), "A"), 2)
        self.assertEqual(due_turn(Pilot(spec(A="easy to reach", B="easy to reach"), echo), "C"), 1)

    def test_not_before_due_and_at_boundary(self):
        p = Pilot(spec(A="hardest to reach", B="easy to reach"), echo)
        p.send_message("A", "hello")             # sent at turn 0, due at 4
        for _ in range(2):
            self.assertEqual(p.read_inbox()["messages"], [])
            p.wait()
        self.assertEqual(p.turn, 3)
        self.assertEqual(p.read_inbox()["messages"], [])
        p.wait()                                  # clock reaches 4: delivered at the advance
        reply = p.events[1]
        self.assertEqual((reply["sent_turn"], reply["due_turn"], reply["delivered_turn"]), (0, 4, 4))
        self.assertEqual(reply["status"], "delivered")  # delivered but not yet agent-visible
        self.assertEqual(p.read_inbox()["messages"][0]["text"], "A re hello @0")
        self.assertEqual((reply["status"], reply["seen_turn"]), ("seen", 4))

    def test_messaging_b_does_not_block_a(self):
        p = Pilot(spec(A="hardest to reach", B="easy to reach"), echo)
        p.send_message("A", "a?")   # turn 0 -> A due 4
        p.send_message("B", "b?")   # turn 1 -> B due 2
        p.wait()                    # turn 3
        self.assertEqual([m["from"] for m in p.read_inbox()["messages"]], ["B"])
        p.wait()                    # turn 4
        self.assertEqual([m["from"] for m in p.read_inbox()["messages"]], ["A"])

    def test_wait_is_one_turn_and_reads_are_free(self):
        p = Pilot(spec(A="easy to reach", B="easy to reach"), echo)
        p.wait()
        self.assertEqual(p.turn, 1)
        for _ in range(5):
            p.read_inbox()
        self.assertEqual(p.turn, 1)
        p.send_message("B", "x")
        self.assertEqual(p.turn, 2)
        self.assertEqual(len(p.read_inbox()["messages"]), 1)  # due 1+1=2, released by the send's advance

    def test_same_turn_order_is_stable_and_exactly_once(self):
        p = Pilot(spec(A="may need follow-up", B="easy to reach"), echo)
        p.send_message("A", "1")    # turn 0 -> due 2
        p.send_message("B", "2")    # turn 1 -> due 2
        got = p.read_inbox()["messages"]
        self.assertEqual([m["from"] for m in got], ["A", "B"])
        p.wait(); p.wait()
        self.assertEqual(p.read_inbox()["messages"], [])
        delivered = [e["id"] for e in p.events if e["kind"] == "reply" and e["delivered_turn"] is not None]
        self.assertEqual(len(delivered), len(set(delivered)), 2)

    def test_pending_hidden_and_silence_is_not_consent(self):
        p = Pilot(spec(A="hardest to reach", B="easy to reach"), lambda *a: "SECRET yes")
        p.send_message("A", "agree?")
        p.send_message("A", "agree??")              # follow-up is logged, not failed
        self.assertTrue(p.events[2]["follow_up"])
        p.read_inbox()
        self.assertNotIn("SECRET", repr(p.observations))
        pending = [e for e in p.events if e["kind"] == "reply"]
        self.assertEqual({e["status"] for e in pending}, {"queued"})
        for e in p.events:
            self.assertFalse({"consent", "refusal", "agreed"} & set(e))

    def test_opening_and_metadata(self):
        p = Pilot(spec(A="easy to reach", B="hardest to reach"), echo, opening="Hi, I'm C.")
        first = p.read_inbox()["messages"]
        self.assertEqual((first[0]["from"], p.events[0]["delivered_turn"], p.turn), ("C", 0, 0))
        self.assertEqual(p.meta["delay_table"],
                         {"easy to reach": 1, "may need follow-up": 2, "hardest to reach": 4})
        self.assertEqual(p.meta["turn_costs"], {"send_message": 1, "wait": 1, "read_inbox": 0})

    def test_personality_does_not_change_delay(self):
        a, b = spec(A="hardest to reach", B="easy to reach"), spec(A="hardest to reach", B="easy to reach")
        b["personalities"]["A"]["option"] = "blunt/direct"
        self.assertEqual(Pilot(a, echo).delays, Pilot(b, echo).delays)


class FamilyWill(unittest.TestCase):
    def test_loads_with_expected_delays(self):
        import json
        spec = json.loads((ROOT / "scenarios/family_will.json").read_text())
        self.assertEqual(Pilot(spec, echo).delays, {"A": 2, "B": 1, "C": 1})


class Archive(unittest.TestCase):
    def test_archive_preserved(self):
        lines = (ROOT / "archive/hospital/MANIFEST.tsv").read_text().splitlines()[1:]
        self.assertEqual(len(lines), 169)
        for line in lines:
            original, archived, sha = line.split("\t")
            self.assertEqual(hashlib.sha256((ROOT / archived).read_bytes()).hexdigest(), sha, archived)

    def test_archive_not_imported(self):
        import msraf
        self.assertEqual(Path(msraf.__file__).parent, ROOT / "msraf")
        for name, module in list(sys.modules.items()):
            self.assertNotIn("archive", str(getattr(module, "__file__", "") or ""), name)


if __name__ == "__main__":
    unittest.main()
