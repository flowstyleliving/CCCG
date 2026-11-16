"""Stakeholder simulator: one model plays each person from their private card.

Each person's simulator sees only: the shared situation (first Narrative paragraph of the
scenario file), the shared rules, its own card, and its own past exchanges with the
agent. It never sees other cards or other people's messages.
"""

import json
import os
from pathlib import Path
import re
import urllib.request

MODEL = "openai/gpt-6-luna"  # OpenRouter "OpenAI: GPT-6 Luna" plays the sisters, MK 2026-11-16 (replaced Nemotron 3 Ultra free)
SETTINGS = {"reasoning_effort": "medium"}     # temperature etc. left at provider defaults
URL = "https://openrouter.ai/api/v1/chat/completions"
# Our wording, not from the scenario file.
# Relationship-neutral: the scenario may be family, neighbours or coworkers.
FRAME = ("You are {who}. An agent helping the people involved in this situation is messaging you. "
         "Reply as {who}, in one short message.")


def quote(text, heading):
    """The blockquote under a '## heading' in the scenario file, unwrapped to one paragraph."""
    block = re.search(rf"## {re.escape(heading)}\n\n((?:> .*\n?)+)", text).group(1)
    return " ".join(line[2:].strip() for line in block.splitlines())


def parse_cards(text):
    situation = re.search(r"## Narrative\n\n(.+?)\n\n", text, re.S).group(1)
    rules = re.search(r"Shared rules for every card:\n(.+?)\n\n", text, re.S).group(1)
    section = re.search(r"## Private cards\n(.+?)\n## ", text, re.S).group(1)
    cards = dict(re.findall(r"^\*\*([A-Z])\*\*[^\n]*\n(.+?)(?=\n\n|\Z)", section, re.S | re.M))
    if set(cards) != {"A", "B", "C"}:
        raise ValueError(f"cards found {sorted(cards)}, need A, B, C")
    return situation, rules, cards


def validate_scenario_md(text, point):
    """Raise ValueError unless the text has every heading and block that the loaders read.

    Checked before a generated scenario is saved and before an episode runs, so a malformed
    scenario fails loudly instead of crashing a loader or silently using the wrong speaker.
    """
    required = ["## Narrative", "## Agent brief", f"## {point}'s opening message",
                "## Private cards", "Shared rules for every card:"]
    missing = [h for h in required if not re.search(rf"^{re.escape(h)}\s*$", text, re.M)]
    missing += [f"card **{w}**" for w in "ABC" if not re.search(rf"^\*\*{w}\*\*", text, re.M)]
    if missing:
        raise ValueError(f"scenario is missing: {', '.join(missing)}")
    try:  # headings exist; the blockquotes and paragraphs under them must also parse
        parse_cards(text)
        quote(text, "Agent brief")
        quote(text, f"{point}'s opening message")
    except AttributeError as exc:
        raise ValueError("scenario has a heading without its blockquote or paragraph") from exc


def _post(payload, key):
    request = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)


class Stakeholders:
    """Callable as Pilot's respond(who, text, turn). Keeps each person's history separately."""

    def __init__(self, scenario_path, seed=None, key=None, text=None):
        """text: the exact scenario text to use; read from scenario_path when omitted."""
        if text is None:
            text = Path(scenario_path).read_text(encoding="utf-8")
        self.situation, self.rules, self.cards = parse_cards(text)
        self.seed, self.key = seed, key or os.environ.get("OPENROUTER_API_KEY")
        self.history = {who: [] for who in self.cards}
        self.calls = []  # private simulator log: request settings and provider response ids
        self.meta = {"model": MODEL, "settings": dict(SETTINGS), "seed": seed, "frame": FRAME,
                     "scenario": str(scenario_path)}

    def system(self, who):
        return "\n\n".join([FRAME.format(who=who), self.situation,
                            "Rules:\n" + self.rules, f"Your card ({who}):\n" + self.cards[who]])

    def __call__(self, who, text, turn):
        if not self.key:
            raise RuntimeError("OPENROUTER_API_KEY not set; no stakeholder reply generated")
        messages = [{"role": "system", "content": self.system(who)}, *self.history[who],
                    {"role": "user", "content": text}]
        payload = {"model": MODEL, "messages": messages, **SETTINGS}
        if self.seed is not None:
            payload["seed"] = self.seed
        body = _post(payload, self.key)
        reply = (body["choices"][0]["message"].get("content") or "").strip()
        if not reply:
            raise RuntimeError(f"empty reply for {who} at turn {turn}")
        self.history[who] += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
        self.calls.append({"who": who, "turn": turn, "id": body.get("id"),
                           "model": body.get("model"), "usage": body.get("usage")})
        return reply
