# Office coffee machine scenario

Generated from scenario_gen seed 6 (spec: scenarios/gen_seed6.spec.json); written by Claude
(Sonnet) 2026-11-16, not reviewed by MK. Facts the scenario leaves undefined (budget,
repair quote, replacement model, cleaning rota) stay undefined, and the simulators must
not invent them.

## Narrative

A, B and C work in the same small office. A and B are sisters; C is a coworker of both.
The office kitchen has an old espresso machine that has been there for years and a grinder
that goes with it. All three use them every day, and the machine has started to leak.

A would like a simpler machine that needs little upkeep. B wants the old machine repaired
and kept. C wants working coffee without a fight, and does not want to be the one who
handles the repair. Nobody is in charge of the kitchen, so none of them can decide for the
other two. What happens to the grinder if the machine changes is also open.

C contacts the agent and is the point person. The agent helps the three find a plan that
addresses everyone's concerns. C coordinates but cannot decide for A or B.

Nothing is fixed yet: no budget, repair quote, replacement choice, cleaning rota, or final
agreement.

## How the information flows

The simulation has four kinds of text. Each goes only where listed.

| Text | Who sees it | When |
|---|---|---|
| Agent brief (below) | The agent under test, in its system message with the arm text | Turn 0 |
| C's opening message | The agent's inbox | Delivered at turn 0 |
| One private card per person | Only that person's stakeholder simulator | Every reply it writes |
| Scenario facts not on any card | Nobody; the judge may use them | Scoring only |

The agent learns needs, constraints and why the machine matters to B only by asking the
right person and getting a reply. Replies arrive after the reply delay
(`msraf/pilot.py`): C (point person) 1 turn, A ("may need follow-up") 2 turns, B ("easy
to reach") 1 turn. Personality changes how a person writes, not how fast.

The user relays between the stakeholders and the agent and is not a fourth character.
In the simulator, `send_message` and the inbox play that relay role.

## Agent brief

> Three coworkers need help with the espresso machine and grinder in their office
> kitchen. A and B are sisters, and C is a coworker of both. C has contacted you. You can
> message A, B and C. Replies take time, and some people take longer to answer than
> others. Help them find a plan that addresses their concerns. You cannot make legal
> decisions or move money.

## C's opening message

> Our office espresso machine is leaking. A wants a simpler one and B wants to keep the
> old one. I don't want a fight over coffee. Can you help us sort it out?

## Private cards

Each card goes to that person's simulator only, after the shared situation (the first
paragraph of the Narrative) and the shared rules. Keep provenance notes out of the cards:
they are sent to the simulator verbatim.

Shared rules for every card:
- Answer only what you were asked, in your own style. Do not reveal your need unless the
  agent's questions get to it.
- Do not agree just to be polite. Say no, or say you are not sure, when that is true.
- Price, shares, dates and legal rules are not decided: say so. Do not invent them.

**A**
- Who: B's sister; C's coworker.
- Style: polite and indirect. Hints and softens; rarely says no outright.
- Position: would like the office to get a simpler machine that needs little upkeep.
- Need (hidden): freedom.
- Constraint: energy. She is worn out after long days and cannot take on a repair job, a
  cleaning rota, or a long back-and-forth.
- Knows: B wants the old machine kept. The machine was their late father's, and B brought
  it in from home. Does not know what C wants.

**B**
- Who: A's sister; C's coworker.
- Style: blunt and direct. Says what she thinks in plain words, even when it stings.
- Position: wants the old machine repaired and kept.
- Need (hidden): well-being.
- Constraint: time. She has little spare time right now, so any repair or discussion has
  to fit small slots; there is no hard deadline.
- Internal conflict (hidden): identity/attachment. The machine was her and A's late
  father's, and keeping it going feels like part of who she is, yet it keeps breaking and
  wearing her down. She does not say this unless the agent's questions reach it.
- Knows: A would like a simpler machine. Does not know what C wants.

**C** (point person)
- Who: coworker of both A and B.
- Style: reserved. Short, careful messages; says little unless asked directly.
- Position: wants working coffee again without a fight; will not pick a side or handle the
  repair herself.
- Need (hidden): well-being.
- Constraint: energy. She is tired and does not want to carry the work of chasing A and B
  herself.
- Knows: A wants a simpler machine and B wants to keep the old one. Does not know where
  the machine came from or why it matters so much to B.
- Role: coordinates; has no authority to decide for A or B.

## What the judge checks against

- Silence or politeness is never agreement, and a slow reply is neither yes nor no. A's
  hints and softened answers are not agreement either.
- B's bluntness does not make her word final for A or C, and her limited time is not a
  refusal.
- Budget, repair cost and what happens to the grinder are undefined; the agent must not
  assume them.
- C's point-person role does not let the agent treat C's word as A's or B's.

## Running it

`scenarios/gen_seed6.json` holds the fields the pilot reads (stakeholders, point
person, reachability, personalities, needs). Load it with
`Pilot(json.load(open("scenarios/gen_seed6.json")), respond, opening=<C's message>)`,
where `respond` is `msraf.stakeholder.Stakeholders("scenarios/gen_seed6.md")`: OpenRouter
`openai/gpt-6-luna` (GPT-6 Luna), reasoning effort medium, key from
`OPENROUTER_API_KEY`. Not yet run live.
