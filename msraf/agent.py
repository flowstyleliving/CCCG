"""Agent loop: the model under test acts in the pilot through tools, one action per call.

Tools: send_message and wait cost 1 turn; read_inbox costs 0; finish ends the episode.
Tool results give the turn number and the count of unread messages, never their contents.
At the turn limit a finalization phase (FINAL_CALLS model calls) still allows read_inbox and finish.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from msraf import stakeholder
from msraf.pilot import Pilot
from toolkits.empathy_geometry_nvc import giraffe

# 2x2 arms: CF toolkit or its style-only control, then active participant or its role placebo.
CF = {True: giraffe.CF_COMPACT_DRAFT, False: giraffe.CF_NEUTRAL_DRAFT}
AP = {True: giraffe.AP_DRAFT, False: giraffe.AP_PLACEBO_DRAFT}
# Character-matched for now (MK 2026-11-16); token-match later.
assert len(CF[True]) == len(CF[False]) and len(AP[True]) == len(AP[False]), "arm lengths differ"


def arm_text(cf, ap):
    return CF[cf] + "\n\n" + AP[ap]

# Models under test (OpenRouter IDs, MK 2026-11-16). All list tools and reasoning_effort.
# GPT-6 Luna is the stakeholder simulator (msraf/stakeholder.py), not a tested model.
TESTED_MODELS = ("anthropic/claude-opus-5.5", "deepseek/deepseek-v4.1-flash-1017", "tencent/hy4",
                 "z-ai/glm-5.3-flash")
SETTINGS = {"reasoning_effort": "medium"}
MAX_TURNS = 20  # shortcut: proposed default, not agreed by MK; set per run with --max-turns
RUNAWAY_TURNS = 100  # with --max-turns 0 (no cap) an episode still stops here; recorded as hit_guard, never shown to the agent
TOOLS = [
    {"type": "function", "function": {"name": "send_message", "description":
        "Send a message to one person. Costs 1 turn. Their reply arrives in your inbox later.",
        "parameters": {"type": "object", "required": ["to", "text"], "properties": {
            "to": {"type": "string", "enum": ["A", "B", "C"]}, "text": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "wait", "description": "Let 1 turn pass.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_inbox", "description":
        "Read messages you have not read yet. Costs no turns.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "finish", "description":
        "End your work. Give a short report of where things stand.",
        "parameters": {"type": "object", "required": ["report"],
                       "properties": {"report": {"type": "string"}}}}},
]


quote = stakeholder.quote
SEMANTICS = {"finalization_phase": True, "version": 2}  # bump when episode rules change; batch resume compares it
FINAL_CALLS = 4
FINAL_MESSAGE = "Turn limit reached. You can still read your inbox and call finish."
ROOT = Path(__file__).resolve().parents[1]
# Allowed (and required) argument names per tool; anything else is rejected before state changes.
ARGS = {"send_message": ("to", "text"), "wait": (), "read_inbox": (), "finish": ("report",)}


def check_args(name, args):
    """Return why the arguments are malformed, or None. Runs before any state changes."""
    if name not in ARGS:
        return None  # unknown tool is reported separately
    if not isinstance(args, dict):
        return "arguments must be a JSON object"
    missing, extra = [k for k in ARGS[name] if k not in args], sorted(set(args) - set(ARGS[name]))
    if missing or extra:
        return f"missing {missing}, unexpected {extra}"
    if name == "send_message" and not (isinstance(args["to"], str) and args["to"] in ("A", "B", "C")):
        return "to must be one of A, B, C"
    for field in {"send_message": ("text",), "finish": ("report",)}.get(name, ()):
        if not isinstance(args[field], str) or not args[field].strip():
            return f"{field} must be a non-empty string"
    return None


def code_rev():
    """Git HEAD and whether the tree has uncommitted changes; None when git is unavailable."""
    def git(*cmd):
        return subprocess.run(["git", *cmd], cwd=ROOT, capture_output=True, text=True, check=True,
                              timeout=30).stdout.strip()
    try:
        return {"head": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.SubprocessError):
        return None


def run_episode(scenario_md, spec, cf, ap, model, seed=None, max_turns=MAX_TURNS, key=None):
    """max_turns=0 means no cap: the agent ends the episode itself, up to RUNAWAY_TURNS."""
    raw = Path(scenario_md).read_bytes()  # exact bytes: hashed, recorded and used for this episode
    text = raw.decode("utf-8")
    point = spec["point_person"]["option"]
    stakeholder.validate_scenario_md(text, point)
    arm = arm_text(cf, ap)
    key = key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set; nothing run")
    if model not in TESTED_MODELS:
        raise ValueError(f"{model} is not a tested model")
    sim = stakeholder.Stakeholders(scenario_md, seed=seed, key=key, text=text)
    pilot = Pilot(spec, sim, opening=quote(text, f"{point}'s opening message"))
    system = arm + "\n\n" + quote(text, "Agent brief")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "You have 1 unread message. Turn 0" + (f" of {max_turns}." if max_turns else ".")}]
    limit = max_turns or RUNAWAY_TURNS
    report, calls = None, []
    # read_inbox is free, so cap model calls too, or a model could read forever.
    final, used, budget = False, 0, 3 * limit
    while report is None:
        if not final and pilot.turn >= limit:
            # Finalization: the clock is at its cap, but reading and reporting cost no turns.
            final, used, budget = True, 0, FINAL_CALLS
            messages.append({"role": "user", "content": FINAL_MESSAGE})
        if used >= budget:
            break
        used += 1
        payload = {"model": model, "messages": messages, "tools": TOOLS,
                   "parallel_tool_calls": False, **SETTINGS}
        if seed is not None:
            payload["seed"] = seed
        body = stakeholder._post(payload, key)
        message = body["choices"][0]["message"]
        calls.append({"id": body.get("id"), "model": body.get("model"), "usage": body.get("usage")})
        messages.append({k: message[k] for k in ("role", "content", "tool_calls") if message.get(k)})
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            messages.append({"role": "user", "content": "Use one of your tools."})
            continue
        for index, call in enumerate(tool_calls):
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
                problem = check_args(name, args)
                if index > 0:
                    result = {"error": "one action per call; this one was not done"}
                elif problem:
                    result = {"error": f"invalid call: {problem}"}
                elif final and name in ("send_message", "wait"):
                    result = {"error": "turn limit reached; only read_inbox and finish still work"}
                elif name == "send_message":
                    result = pilot.send_message(args["to"], args["text"])
                elif name == "wait":
                    result = pilot.wait()
                elif name == "read_inbox":
                    result = pilot.read_inbox()
                elif name == "finish":
                    report, result = args["report"], {"finished": True}
                else:
                    result = {"error": f"unknown tool {name}"}
            except (KeyError, TypeError, ValueError) as exc:  # JSONDecodeError is a ValueError
                result = {"error": f"invalid call: {exc}"}
            result = {**result, "turn": pilot.turn, **({"of": max_turns} if max_turns else {}),
                      "unread": len(pilot._inbox) - pilot._seen}
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    # call_budget: model calls ran out before the clock reached its cap (not a turn cap).
    termination = ("finished" if report is not None else
                   ("turn_cap" if max_turns else "runaway_guard") if final else "call_budget")
    return {"meta": {"agent_model": model, "agent_settings": dict(SETTINGS), "seed": seed,
                     "max_turns": max_turns or None, "runaway_guard": None if max_turns else RUNAWAY_TURNS, "cf": cf, "ap": ap, "arm_sha256": hashlib.sha256(arm.encode()).hexdigest(),
                     "arm_text": arm, "system": system,
                     "semantics": dict(SEMANTICS),
                     # Reproducibility record: everything that defines the episode's inputs.
                     "scenario_sha256": hashlib.sha256(raw).hexdigest(), "scenario_text": text,
                     "spec": spec, "tools": TOOLS, "code_rev": code_rev(),
                     "seeds": {"episode_seed": seed, "scenario_generation_seed": spec.get("seed")},
                     "pilot": pilot.meta, "simulator": sim.meta},
            "end": {"turn": pilot.turn, "finished": report is not None, "report": report,
                    "hit_guard": not max_turns and report is None, "termination": termination},
            "transcript": messages, "agent_calls": calls, "events": pilot.events,
            "observations": pilot.observations, "simulator_calls": sim.calls}


def save(result, out_dir):
    """Write every file into a temp dir beside the target, then rename it: a run folder is all or nothing."""
    out = Path(out_dir)
    if out.exists():
        raise FileExistsError(out)  # never overwrite a saved run
    out.parent.mkdir(parents=True, exist_ok=True)
    result["meta"]["saved_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    tmp = Path(tempfile.mkdtemp(prefix=f".{out.name}.tmp-", dir=out.parent))
    try:
        for name, value in result.items():
            (tmp / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        (tmp / "scenario.md").write_bytes(result["meta"]["scenario_text"].encode("utf-8"))
        (tmp / "spec.json").write_text(json.dumps(result["meta"]["spec"], indent=2) + "\n", encoding="utf-8")
        os.rename(tmp, out)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", default="scenarios/family_will")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--model", choices=TESTED_MODELS, required=True)
    parser.add_argument("--cf", choices=("on", "off"), required=True)
    parser.add_argument("--ap", choices=("on", "off"), required=True)
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    spec = json.loads(Path(args.scenario + ".json").read_text())
    print(save(run_episode(args.scenario + ".md", spec, args.cf == "on", args.ap == "on", args.model, seed=args.seed,
                           max_turns=args.max_turns), args.out))


if __name__ == "__main__":
    main()
