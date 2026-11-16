import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scenario_gen import scenario
from scenario_gen.generate import generate


def valid_md(seed):
    """Minimal scenario that passes validation, with the opening heading of that seed's point person."""
    point = generate(seed)["point_person"]["option"]
    return (f"## Narrative\n\nSituation.\n\n## Agent brief\n\n> Brief.\n\n## {point}'s opening message\n\n"
            "> Hello.\n\n## Private cards\n\nShared rules for every card:\n- Be brief.\n\n"
            "**A**\nCard a.\n\n**B**\nCard b.\n\n**C**\nCard c.\n\n## Judge\n")


class ScenarioTest(unittest.TestCase):
    def test_codex_fallback_saves_run(self):
        # No live model call: fake the two codex subprocess calls.
        def fake_run(cmd, **kw):
            if cmd[1] == "--version":
                return mock.Mock(stdout="codex-cli 0.0.0\n")
            Path(cmd[cmd.index("-o") + 1]).write_text(valid_md(7), encoding="utf-8")
            assert kw["input"].startswith(scenario.PROMPT_PATH.read_text(encoding="utf-8"))
            return mock.Mock()

        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(scenario.subprocess, "run", side_effect=fake_run):
            run = scenario.make_scenario(7, tmp)
            meta = json.loads((run / "meta.json").read_text())
            self.assertEqual(meta["backend"], "codex-cli")
            self.assertEqual(meta["cli_version"], "codex-cli 0.0.0")
            self.assertEqual(json.loads((run / "spec.json").read_text())["seed"], 7)
            self.assertEqual((run / "scenario.md").read_text(), valid_md(7))
            with self.assertRaises(FileExistsError):  # a saved scenario is never overwritten
                scenario.make_scenario(7, tmp)

    def test_api_used_when_key_given(self):
        with mock.patch.dict(os.environ, {"SCENARIO_API_KEY": "k"}), \
                mock.patch.object(scenario, "via_api", return_value=(valid_md(3), {"backend": "api"})) as api, \
                mock.patch.object(scenario, "via_codex") as codex, \
                tempfile.TemporaryDirectory() as tmp:
            scenario.make_scenario(3, tmp)
            api.assert_called_once()
            codex.assert_not_called()

    def test_invalid_scenario_raises_and_saves_nothing(self):
        for bad in ("A scenario.", valid_md(7).replace("## Private cards", "## Cards"),
                    valid_md(7).replace("**B**", "**X**")):
            with mock.patch.object(scenario, "via_codex", return_value=(bad, {"backend": "codex-cli"})), \
                    mock.patch.dict(os.environ, {}, clear=True), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    scenario.make_scenario(7, tmp)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_opening_heading_follows_point_person(self):
        wrong = "B" if generate(7)["point_person"]["option"] == "A" else "A"
        text = valid_md(7).replace(f"## {generate(7)['point_person']['option']}'s", f"## {wrong}'s")
        with self.assertRaises(ValueError):
            scenario.validate_scenario_md(text, generate(7)["point_person"]["option"])


if __name__ == "__main__":
    unittest.main()
