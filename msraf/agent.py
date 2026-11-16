"""Agent loop: the model under test acts in the pilot through tools, one action per call.

Tools: send_message and wait cost 1 turn; read_inbox costs 0; finish ends the episode.
Tool results give the turn number and the count of unread messages, never their contents.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re

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


def quote(text, heading):
    """The blockquote under a '## heading' in the scenario file, unwrapped to one paragraph."""
    block = re.search(rf"## {re.escape(heading)}\n\n((?:> .*\n?)+)", text).group(1)
    return " ".join(line[2:].strip() for line in block.splitlines())


def run_episode(scenario_md, spec, cf, ap, model, seed=None, max_turns=MAX_TURNS, key=None):
    text = Path(scenario_md).read_text(encoding="utf-8")
    arm = arm_text(cf, ap)
    key = key or os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set; nothing run")
    if model not in TESTED_MODELS:
        raise ValueError(f"{model} is not a tested model")
    sim = stakeholder.Stakeholders(scenario_md, seed=seed, key=key)
    pilot = Pilot(spec, sim, opening=quote(text, "C's opening message"))
    system = arm + "\n\n" + quote(text, "Agent brief")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": "You have 1 unread message. Turn 0 of " f"{max_turns}."}]
    report, calls = None, []
    # read_inbox is free, so cap model calls too, or a model could read forever.
    for _ in range(3 * max_turns):
        if report is not None or pilot.turn >= max_turns:
            break
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
                if index > 0:
                    result = {"error": "one action per call; this one was not done"}
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
            except (KeyError, ValueError, json.JSONDecodeError) as exc:
                result = {"error": f"invalid call: {exc}"}
            result = {**result, "turn": pilot.turn, "of": max_turns,
                      "unread": len(pilot._inbox) - pilot._seen}
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result)})
    return {"meta": {"agent_model": model, "agent_settings": dict(SETTINGS), "seed": seed,
                     "max_turns": max_turns, "cf": cf, "ap": ap, "arm_sha256": hashlib.sha256(arm.encode()).hexdigest(),
                     "arm_text": arm, "system": system,
                     "pilot": pilot.meta, "simulator": sim.meta},
            "end": {"turn": pilot.turn, "finished": report is not None, "report": report},
            "transcript": messages, "agent_calls": calls, "events": pilot.events,
            "observations": pilot.observations, "simulator_calls": sim.calls}


def save(result, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=False)  # never overwrite a saved run
    result["meta"]["saved_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for name, value in result.items():
        (out / f"{name}.json").write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
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
