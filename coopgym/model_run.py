"""Run real models in the simulator through coopgym.adapter.

  python3 -m coopgym.model_run --backend claude --name claude --out runs/R
  python3 -m coopgym.model_run --backend codex --name codex --out runs/R
  python3 -m coopgym.model_run --backend chat --name qwen14b --url http://127.0.0.1:8091 --model ID --out runs/R
  python3 -m coopgym.model_run --summarize runs/R [--json]

Each backend run plays all five variants once, in shuffled order, in opaque
episode directories (e1..e5). The variant map and run metadata live in the run
root, outside the episode directories. --summarize rescores every action log
with the unchanged scorers and prints the same tables as coopgym.run.
"""

import argparse
import json
import random
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from .adapter import CHAT_INVOKE, MAX_STEPS, SHELL_INVOKE, TASK_PROMPT, Episode
from .run import print_tables
from .scenario import SCENARIOS
from .scoring import twin_pair_correct

ADAPTER = Path(__file__).resolve().parent / "adapter.py"
EPISODE_SECONDS = 40 * 60
# Everything except the ./step command is denied, so the agent cannot read the
# simulator source, the variant map, or other files.
CLAUDE_DENY = ["Read", "Edit", "Write", "Glob", "Grep", "NotebookEdit", "WebFetch",
               "WebSearch", "Task", "Skill", "Monitor", "CronCreate", "SendMessage"]

THINK = re.compile(r"<think>.*?</think>", re.S)
STEP_HEAD = re.compile(r"^\s*STEP\s+([A-Za-z_]+)[ \t]*", re.M)


def parse_reply(reply):
    """Return ("step", tool, args), ("done", None, None) or ("invalid", None, None).

    The JSON object is decoded from just after the tool name, so trailing text
    on the same line (for example `STEP report {...}DONE`) does not lose the step.
    """
    text = THINK.sub("", reply)
    match = STEP_HEAD.search(text)
    if match:
        rest = text[match.end():]
        if not rest.startswith("{"):
            # A tool with no arguments: nothing but an optional DONE may follow.
            line = rest.split("\n", 1)[0].strip()
            return ("step", match.group(1), {}) if line in ("", "DONE") else ("invalid", None, None)
        try:
            args, _ = json.JSONDecoder().raw_decode(rest)
        except json.JSONDecodeError:
            return "invalid", None, None
        return ("step", match.group(1), args) if isinstance(args, dict) else ("invalid", None, None)
    if re.search(r"^\s*DONE\s*$", text, re.M):
        return "done", None, None
    return "invalid", None, None


def _chat(url, model, messages, max_tokens):
    body = json.dumps({"model": model, "messages": messages, "temperature": 0.0,
                       "max_tokens": max_tokens}).encode()
    request = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=900) as response:
        return json.load(response)["choices"][0]["message"]["content"] or ""


def run_chat(episode, log_path, url, model, max_tokens, deadline):
    messages = [{"role": "system", "content": TASK_PROMPT},
                {"role": "user", "content": CHAT_INVOKE}]
    invalid, stop = 0, "turn limit"
    with open(log_path, "w") as log:
        for _ in range(MAX_STEPS + 10):
            if time.time() > deadline:
                stop = "time limit"
                break
            reply = _chat(url, model, messages, max_tokens)
            log.write(json.dumps({"assistant": reply}) + "\n")
            messages.append({"role": "assistant", "content": reply})
            kind, tool, args = parse_reply(reply)
            if kind == "done":
                stop = "done"
                break
            if kind == "invalid":
                invalid += 1
                if invalid > 5:
                    stop = "unparseable replies"
                    break
                feedback = "Could not parse that. Reply with exactly one line: STEP TOOL JSON, or DONE."
            else:
                result = episode.step(tool, args)
                feedback = json.dumps(result)
                if result.get("error") == "step limit reached":
                    stop = "step limit"
                    break
            log.write(json.dumps({"user": feedback}) + "\n")
            messages.append({"role": "user", "content": feedback})
    return stop


def _write_wrapper(episode_dir, manifest_path):
    wrapper = episode_dir / "step"
    wrapper.write_text("#!/bin/sh\n"
                       f"COOPGYM_MANIFEST='{manifest_path}' exec python3 -I '{ADAPTER}' step \"$@\"\n")
    wrapper.chmod(0o755)


def run_shell_agent(backend, episode_dir, log_path):
    prompt = TASK_PROMPT + "\n" + SHELL_INVOKE
    if backend == "claude":
        cmd = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--setting-sources", "project", "--strict-mcp-config",
               "--no-session-persistence", "--allowedTools", "Bash(./step:*)",
               "--disallowedTools", *CLAUDE_DENY]
        stdin = None
    else:
        # Codex default model: the configured one is rejected on this account.
        cmd = ["codex", "exec", "--ignore-user-config", "-c", 'model_reasoning_effort="high"',
               "--sandbox", "workspace-write", "--skip-git-repo-check", "--color", "never",
               "-C", str(episode_dir), "-"]
        stdin = prompt
    with open(log_path, "w") as log:
        try:
            done = subprocess.run(cmd, cwd=episode_dir, input=stdin, text=True, stdout=log,
                                  stderr=subprocess.STDOUT, timeout=EPISODE_SECONDS)
            return f"exit {done.returncode}"
        except subprocess.TimeoutExpired:
            return "time limit"


def run_backend(args):
    root = Path(args.out).resolve()
    model_dir = root / args.name
    model_dir.mkdir(parents=True, exist_ok=False)
    (model_dir / "logs").mkdir()
    variants = list(SCENARIOS)
    random.Random(args.seed).shuffle(variants)
    manifest = {}
    for index, variant in enumerate(variants, 1):
        episode_dir = model_dir / f"e{index}"
        episode_dir.mkdir()
        manifest[str(episode_dir.resolve())] = variant
    manifest_path = root / f".manifest_{args.name}.json"
    manifest_path.write_text(json.dumps(manifest, indent=1))
    meta = {"name": args.name, "backend": args.backend, "requested_model": args.model,
            "seed": args.seed, "episodes": {}}
    for episode_path, variant in manifest.items():
        episode_dir = Path(episode_path)
        log_path = model_dir / "logs" / f"{episode_dir.name}.log"
        started = time.time()
        if args.backend == "chat":
            stop = run_chat(Episode(episode_dir, variant), log_path, args.url, args.model,
                            args.max_tokens, started + EPISODE_SECONDS)
        else:
            _write_wrapper(episode_dir, manifest_path)
            stop = run_shell_agent(args.backend, episode_dir, log_path)
        meta["episodes"][episode_dir.name] = {"stop": stop, "seconds": round(time.time() - started)}
        (root / f".meta_{args.name}.json").write_text(json.dumps(meta, indent=1))
        print(f"{args.name} {episode_dir.name}: {stop} in {meta['episodes'][episode_dir.name]['seconds']} s",
              flush=True)


def _model_evidence(root, name, meta):
    """Model id as reported by the tool itself, not as assumed."""
    found = set()
    for log in sorted((root / name / "logs").glob("*.log")):
        text = log.read_text(errors="replace")
        if meta["backend"] == "claude":
            found.update(re.findall(r'"subtype":\s*"init".*?"model":\s*"([^"]+)"', text))
        elif meta["backend"] == "codex":
            found.update(re.findall(r"^model: (\S+)", text, re.M))
    if meta["backend"] == "chat":
        found.add(meta["requested_model"] + " (requested from local server)")
    return sorted(found) or ["unknown"]


def summarize(root, as_json=False, only=None):
    root = Path(root).resolve()
    episodes = {variant: {} for variant in SCENARIOS}
    pairs, models = {}, {}
    for manifest_path in sorted(root.glob(".manifest_*.json")):
        name = manifest_path.stem[len(".manifest_"):]
        if only and name not in only:
            continue
        meta = json.loads((root / f".meta_{name}.json").read_text())
        manifest = json.loads(manifest_path.read_text())
        scored = {}
        for episode_path, variant in manifest.items():
            result = Episode(episode_path, variant).score()
            result["stop"] = meta["episodes"].get(Path(episode_path).name, {}).get("stop", "not run")
            scored[variant] = result
            episodes[variant][name] = result
        pairs[name] = twin_pair_correct(scored["allowed_twin"]["scores"],
                                        scored["forbidden_twin"]["scores"])
        models[name] = _model_evidence(root, name, meta)
    result = {"episodes": episodes, "twin_pair_correct": pairs, "models": models}
    if as_json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return result
    print_tables(result)
    for name, ids in models.items():
        steps = {v: episodes[v][name]["steps"] for v in SCENARIOS}
        stops = {v: episodes[v][name]["stop"] for v in SCENARIOS}
        print(f"{name}: model {', '.join(ids)}; steps {steps}; stop {stops}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["claude", "codex", "chat"])
    parser.add_argument("--name")
    parser.add_argument("--out", help="run root, for example runs/2026-10-31")
    parser.add_argument("--url", default="http://127.0.0.1:8091")
    parser.add_argument("--model", default="")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--summarize", metavar="RUN_ROOT")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--only", help="comma-separated model names to summarize")
    args = parser.parse_args()
    if args.summarize:
        summarize(args.summarize, args.json, args.only.split(",") if args.only else None)
    elif args.backend and args.name and args.out:
        run_backend(args)
    else:
        parser.error("give --backend, --name and --out, or --summarize RUN_ROOT")


if __name__ == "__main__":
    main()
