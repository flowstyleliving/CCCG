# Cooperation Gym

> **Status: in design.** This repository holds a design sketch only. There is no code, no data, and no results yet. Everything below describes what is planned, not what has been built or measured.

## The question

When an AI agent works on a task that affects several people, does it meet their actual needs, or does it only satisfy whoever is grading it? And when one of those people corrects it partway through, does it take the correction on board?

Most agent benchmarks score a task against one objective. Real work usually serves several stakeholders whose needs overlap and sometimes conflict. The Cooperation Gym is a planned benchmark that scores an agent against each stakeholder's needs separately.

## Planned design

- **Several stakeholders per task.** Each scenario has two or more simulated stakeholders, each with private needs written in advance (for example, a need for safety, for being consulted, or for predictability). The agent sees the task and what each stakeholder says, not the need cards themselves.
- **Twin scenarios.** Each scenario comes as a matched pair that differs in one controlled detail, so a difference in the agent's score can be traced to that detail.
- **Corrections mid-task.** A stakeholder can interrupt partway through and say what isn't working for them. The benchmark records whether the agent changes course, how far, and whether it keeps meeting the other stakeholders' needs while it does.
- **Per-stakeholder scoring.** Each stakeholder's needs are scored separately against their need card, not folded into a single satisfaction number.

## Planned comparison

One planned experiment compares two ways of correcting an agent's failures on the same tasks:

1. **Blame framing:** the failure is marked wrong.
2. **Need-and-cost framing:** the correction names whose need went unmet, what that cost, and how to repair it.

The test is whether the cooperative behavior holds when the oversight cue changes or is removed. If the two framings show no difference, that counts against the idea.

## Open questions

- What exactly differs between the two scenarios in each twin pair.
- How need cards are written and checked so that they don't leak into what the agent sees.
- How to judge whether a stakeholder's need was met: a human rater, a model judge, or both, and how to check one against the other.
- How to tell a real change of course apart from surface agreement with whoever spoke last.

## Not claimed

No part of this benchmark has been implemented, run, or validated. It is not yet evidence about any model.

## Author

Michael S. R. Kitti · github.com/flowstyleliving
