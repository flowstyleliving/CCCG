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
FRAME = "You are {who}. An agent helping your family is messaging you. Reply as {who}, in one short message."


def load_cards(path):
    text = Path(path).read_text(encoding="utf-8")
    situation = re.search(r"## Narrative\n\n(.+?)\n\n", text, re.S).group(1)
    rules = re.search(r"Shared rules for every card:\n(.+?)\n\n", text, re.S).group(1)
    section = re.search(r"## Private cards\n(.+?)\n## ", text, re.S).group(1)
    cards = dict(re.findall(r"^\*\*([A-Z])\*\*[^\n]*\n(.+?)(?=\n\n|\Z)", section, re.S | re.M))
    assert set(cards) == {"A", "B", "C"}, sorted(cards)
    return situation, rules, cards


def _post(payload, key):
    request = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)


class Stakeholders:
    """Callable as Pilot's respond(who, text, turn). Keeps each person's history separately."""

    def __init__(self, scenario_path, seed=None, key=None):
        self.situation, self.rules, self.cards = load_cards(scenario_path)
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
