"""Turn a generated spec into a scenario with the scenario model (design/scenario_generator.md).

Backend rule: if SCENARIO_API_KEY is set, call the OpenAI API with it. Otherwise run the
Codex CLI on the user's own ChatGPT subscription. Every run saves the spec, prompt,
scenario and metadata so the exact scenario can be reused without regenerating it.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request

from scenario_gen.generate import generate

MODEL = "gpt-6-astra"
PROMPT_PATH = Path(__file__).with_name("scenario_prompt.md")
# --ignore-user-config keeps the user's own Codex settings and AGENTS.md out of the run.
CODEX_FLAGS = ["exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
               "-s", "read-only", "-m", MODEL]


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def via_api(prompt, key):
    # shortcut: untested against the live API (no paid runs yet); verify response parsing on first use.
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps({"model": MODEL, "input": prompt}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = json.load(response)
    text = "".join(part["text"] for item in body["output"] if item.get("type") == "message"
                   for part in item["content"] if part.get("type") == "output_text")
    return text, {"backend": "api", "endpoint": "v1/responses", "response_id": body.get("id"),
                  "response_model": body.get("model")}


def via_codex(prompt):
    version = subprocess.run(["codex", "--version"], capture_output=True, text=True,
                             check=True).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "last.md"
        subprocess.run(["codex", *CODEX_FLAGS, "-C", tmp, "-o", str(out), "-"],
                       input=prompt, capture_output=True, text=True, check=True, timeout=1800)
        text = out.read_text(encoding="utf-8")
    return text, {"backend": "codex-cli", "cli_version": version, "flags": CODEX_FLAGS}


def make_scenario(seed, out_dir):
    spec = generate(seed)
    template = PROMPT_PATH.read_text(encoding="utf-8")
    prompt = template + "\n" + json.dumps(spec, indent=2) + "\n"
    key = os.environ.get("SCENARIO_API_KEY")
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    text, backend = via_api(prompt, key) if key else via_codex(prompt)
    if not text.strip():
        raise RuntimeError("scenario model returned an empty scenario; nothing saved")
    run = Path(out_dir) / f"seed-{spec['seed']}"
    run.mkdir(parents=True, exist_ok=False)  # never overwrite a saved scenario
    (run / "spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (run / "prompt.txt").write_text(prompt, encoding="utf-8")
    (run / "scenario.md").write_text(text, encoding="utf-8")
    meta = {"model": MODEL, **backend, "started_utc": started,
            "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "prompt_template_sha256": _sha(template), "prompt_sha256": _sha(prompt),
            "scenario_sha256": _sha(text)}
    (run / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("scenarios"))
    args = parser.parse_args()
    print(make_scenario(args.seed, args.out_dir))


if __name__ == "__main__":
    main()
