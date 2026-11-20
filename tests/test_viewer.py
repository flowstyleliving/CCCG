import json
import re
import tempfile
import unittest
from pathlib import Path

from msraf import viewer


def write(d, name, obj):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(json.dumps(obj), encoding="utf-8")


def event(kind, who, text, sent, due=None, delivered=None, seen=None, status=None):
    return {"id": 0, "kind": kind, "stakeholder": who, "text": text, "in_reply_to": None, "sent_turn": sent,
            "due_turn": due, "delivered_turn": delivered, "seen_turn": seen, "status": status}


class Viewer(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name) / "my-run"
        # A current-schema 50-turn episode with both score files and text that would close a <script> tag.
        new = self.run / "tencent-hy4_cf1_ap0_s2"
        write(new, "meta.json", {"agent_model": "tencent/hy4", "cf": True, "ap": False, "seed": 2, "max_turns": 50,
                                 "spec": {"point_person": {"option": "B"}}})
        write(new, "end.json", {"turn": 37, "finished": True, "report": "done </script><b>x</b>",
                                "hit_guard": False, "termination": "finished"})
        write(new, "events.json", [event("opening", "B", "hi", 0, 0, 0, 0, "seen"),
                                   event("agent_message", "A", "q", 1),
                                   event("reply", "A", "a", 1, 5, 5, None, "delivered")])
        write(new, "score_v2.json", {"scores": {"cooperation": 0.5, "corrigibility": 1.0, "candor": 0.83},
                                     "verdicts": {"coop_asked_why": {"pass": False, "evidence": "e"}}})
        write(new, "score.json", {"scores": {"cooperation": 0.0}, "verdicts": {}})
        # An old-schema, unscored, uncapped episode: no spec in meta, no termination in end.json.
        old = self.run / "glm_cf0_ap0_s1"
        write(old, "meta.json", {"agent_model": "z-ai/glm", "cf": False, "ap": False, "seed": 1, "max_turns": None})
        write(old, "end.json", {"turn": 3, "finished": False, "report": None})
        write(old, "events.json", [event("opening", "C", "hello", 0, 0, 0, 0, "seen")])
        (self.run / "not-an-episode").mkdir()
        (self.run / "viewer.html").write_text("old output")

    def tearDown(self):
        self.tmp.cleanup()

    def test_collects_both_schemas(self):
        eps = {e["id"]: e for e in viewer.collect(self.run)}
        self.assertEqual(sorted(eps), ["glm_cf0_ap0_s1", "tencent-hy4_cf1_ap0_s2"])
        new, old = eps["tencent-hy4_cf1_ap0_s2"], eps["glm_cf0_ap0_s1"]
        self.assertEqual((new["score_file"], new["scores"]["cooperation"], new["point"], new["max_turns"]),
                         ("score_v2.json", 0.5, "B", 50))
        self.assertEqual(new["events"][2]["delivered_turn"], 5)
        self.assertEqual((old["score_file"], old["scores"], old["verdicts"], old["point"], old["max_turns"], old["termination"]),
                         (None, None, {}, "C", None, "not finished"))

    def test_page_embeds_data_safely_and_needs_no_network(self):
        eps = viewer.collect(self.run)
        html = viewer.render(self.run, eps)
        self.assertNotIn("__TRACE_DATA__", html)
        self.assertIsNone(re.search(r"https?://", html))  # no CDN, font or API: opens offline from disk
        blob = re.search(r'<script id="trace-data" type="application/json">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(blob), {"run": "my-run", "episodes": eps})

    def test_cli_writes_default_output(self):
        import subprocess, sys
        out = subprocess.run([sys.executable, "-m", "msraf.viewer", str(self.run)], capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parents[1], check=True)
        self.assertIn("(2 episodes)", out.stdout)
        self.assertIn('id="trace-data"', (self.run / "viewer.html").read_text())

    def test_empty_folder_fails_clearly(self):
        with self.assertRaises(SystemExit):
            viewer.collect(self.run / "not-an-episode")


if __name__ == "__main__":
    unittest.main()
