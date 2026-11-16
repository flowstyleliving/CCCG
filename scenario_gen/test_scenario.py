import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scenario_gen import scenario


class ScenarioTest(unittest.TestCase):
    def test_codex_fallback_saves_run(self):
        # No live model call: fake the two codex subprocess calls.
        def fake_run(cmd, **kw):
            if cmd[1] == "--version":
                return mock.Mock(stdout="codex-cli 0.0.0\n")
            Path(cmd[cmd.index("-o") + 1]).write_text("A scenario.", encoding="utf-8")
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
            self.assertEqual((run / "scenario.md").read_text(), "A scenario.")
            with self.assertRaises(FileExistsError):  # a saved scenario is never overwritten
                scenario.make_scenario(7, tmp)

    def test_api_used_when_key_given(self):
        with mock.patch.dict(os.environ, {"SCENARIO_API_KEY": "k"}), \
                mock.patch.object(scenario, "via_api", return_value=("S.", {"backend": "api"})) as api, \
                mock.patch.object(scenario, "via_codex") as codex, \
                tempfile.TemporaryDirectory() as tmp:
            scenario.make_scenario(3, tmp)
            api.assert_called_once()
            codex.assert_not_called()


if __name__ == "__main__":
    unittest.main()
