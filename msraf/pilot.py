"""Turn-based asynchronous messaging for the MSRAF pilot (no minutes, no wall clock).

Turn semantics (the one delivery boundary):
- The clock starts at turn 0. The point person's opening message is delivered at turn 0,
  before the agent's first action.
- An action taken at turn t is stamped t. A turn-consuming action then moves the clock to
  t + 1, and every reply due at or before t + 1 is delivered into the inbox right away,
  before the agent's next action. So the boundary is: after an action, at the clock advance.
- A message sent at turn t gets its reply due at turn t + delay, and that reply is in the
  inbox when the agent acts at turn t + delay.
- Turn cost: send_message = 1, wait = 1, read_inbox = 0. read_inbox only returns delivered
  messages the agent has not seen yet; it never moves the clock or delivers anything.
- Replies due together are delivered in send order (stable event id), each exactly once.

Delay is neither consent nor refusal: an undelivered reply only has status "queued".
"""

import heapq

from scenario_gen.generate import REACHABILITY

# Reply delay in turns, keyed by the reachability category NAME, never the roll number.
# The generator's rating 1 = "hardest to reach", 2 = "may need follow-up", 3 = "easy to
# reach" (scenario_gen/generate.py REACHABILITY), so rating numbers are not delays.
DELAYS = {"easy to reach": 1, "may need follow-up": 2, "hardest to reach": 4}
POINT_PERSON_DELAY = 1  # no reachability roll; coordinating role, no authority over others
TURN_COSTS = {"send_message": 1, "wait": 1, "read_inbox": 0}
assert set(DELAYS) == set(REACHABILITY), "delay table out of sync with the generator"


class Pilot:
    def __init__(self, spec, respond, opening=None):
        """respond(stakeholder, text, turn) -> reply text: the stakeholder simulator.

        It is called when a message is sent; the reply stays private until delivered.
        """
        self.point = spec["point_person"]["option"]
        self.delays = {p: DELAYS[r["option"]] for p, r in spec["reachability"].items()}
        self.delays[self.point] = POINT_PERSON_DELAY
        assert set(self.delays) == set(spec["stakeholders"])
        self.respond = respond
        self.turn = 0
        self.events = []        # private simulator record, one entry per message
        self._queue = []        # (due_turn, event_id) of undelivered replies
        self._inbox = []        # delivered event ids, in delivery order
        self._seen = 0          # how many inbox entries the agent has read
        self.observations = []  # exactly what the agent was shown, per call
        self.meta = {"seed": spec.get("seed"), "point_person": self.point,
                     "delays": dict(self.delays), "delay_table": dict(DELAYS),
                     "point_person_delay": POINT_PERSON_DELAY, "turn_costs": dict(TURN_COSTS),
                     "boundary": "after each turn-consuming action, at the clock advance; "
                                 "opening message at turn 0 before the first action"}
        if opening is not None:
            self._new("opening", self.point, opening, None, 0, 0)
            self._deliver()

    def _new(self, kind, who, text, in_reply_to, sent, due):
        event = {"id": len(self.events), "kind": kind, "stakeholder": who, "text": text,
                 "in_reply_to": in_reply_to, "sent_turn": sent, "due_turn": due,
                 "delivered_turn": None, "seen_turn": None, "status": "queued"}
        self.events.append(event)
        if due is not None:
            heapq.heappush(self._queue, (due, event["id"]))
        return event

    def _deliver(self):
        while self._queue and self._queue[0][0] <= self.turn:
            event = self.events[heapq.heappop(self._queue)[1]]
            event["delivered_turn"], event["status"] = self.turn, "delivered"
            self._inbox.append(event["id"])

    def _advance(self):
        self.turn += 1
        self._deliver()

    def _observe(self, action, result):
        self.observations.append({"turn": self.turn, "action": action, **result})
        return result

    def send_message(self, to, text):
        if to not in self.delays:
            raise ValueError(f"unknown stakeholder {to!r}")
        sent = self.turn
        # Logged only; a follow-up is not a failure without a predefined rubric rule.
        follow_up = any(e["stakeholder"] == to and e["kind"] == "reply" and e["status"] == "queued"
                        for e in self.events)
        message = self._new("agent_message", to, text, None, sent, None)
        message.update(status="sent", follow_up=follow_up)
        self._new("reply", to, self.respond(to, text, sent), message["id"], sent,
                  sent + self.delays[to])
        self._advance()
        return self._observe("send_message", {"sent_turn": sent, "message_id": message["id"]})

    def wait(self):
        self._advance()
        return self._observe("wait", {})

    def read_inbox(self):
        new = [self.events[i] for i in self._inbox[self._seen:]]
        self._seen = len(self._inbox)
        for event in new:
            event["seen_turn"], event["status"] = self.turn, "seen"
        return self._observe("read_inbox", {"messages": [
            {"id": e["id"], "from": e["stakeholder"], "in_reply_to": e["in_reply_to"],
             "text": e["text"]} for e in new]})
