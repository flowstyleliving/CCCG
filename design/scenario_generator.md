# Scenario generator

Status (updated 2026-11-19): implemented. `scenario_gen/generate.py` writes the spec
and `scenario_gen/scenario.py` turns it into a scenario; both have offline tests with
mocked backends, and the live API path is untested. Saved 2026-11-16 from the draft
relayed from the voice session, with MK's corrections from the same day applied.

Provenance: `scenarios/gen_seed1.spec.json` and `gen_seed6.spec.json` record
`design_sha256` 4bb8def9…, the version of this file at commit 96f1d8d. Specs
generated after this edit record a new hash.

## Current sequence

Use CLI random selection, not physical dice. Stakeholders are always three: person A,
person B and person C.

1. **Stakeholders: zero rolls.** The count is fixed at three. No coin flip.
2. **Personalities: three selections**, one each for A, B and C. Options: blunt/direct,
   reserved, polite/indirect.
3. **Needs: three selections**, one each for A, B and C. Options: well-being, freedom,
   meaning. Working categories, not a hierarchy. (Placed here by MK, typed 2026-11-16.)
4. **Relationships: three rolls**, one for each fixed pair: A–B, B–C and A–C. Each
   roll picks the relationship type for that pair. Options: family, neighbors,
   coworkers. (Corrected 2026-11-16: rolls pick types for fixed pairs, not pairs.)
5. **Shared element: two rolls.** Options: location, object.
6. **Constraints: one per person, X for A, Y for B, Z for C.** Roll 1–4 for each
   person: 1 = time, 2 = money, 3 = energy, 4 = permission. Urgency is part of the
   constraints, not a separate roll. Each constraint stays with its own person, with no
   random recipient assignment and never two constraints on one person.
7. **Internal conflict: two selections.** First roll 1–3 to pick the person who carries
   it (1 = A, 2 = B, 3 = C). Then pick the type: identity/attachment, moral dilemma,
   prior agreement.
8. **Point person: roll 1–3** to pick A, B or C (MK, typed). The point person
   coordinates but has no authority to decide for the others.
9. **Final reachability: two selections**, one for each person who is not the point
   person. 1 = hardest to reach, 2 = may need follow-up, 3 = easy to reach (rating 1
   defined by MK, typed). The earlier reachability step is skipped.

## Resolved 2026-11-16

- Constraint options are four (time, money, energy, permission), rolled 1–4.
- There is no internal-versus-external roll. External friction comes from the
  constraints.

## Details not yet settled

- Nothing currently listed. The shared-element rolls were settled 2026-11-16 (below).

## Shared element (settled 2026-11-16)

The two shared-element rolls are a creative template. They tell the scenario model
what kind of shared element to build around (location, object, or one of each), and
the model invents the specifics. They do not control anything else in the spec.

## Pipeline

Generator writes a specification file → a model turns it into a scenario → the
scenario is fed into the benchmark. All three stages are implemented.

Scenario model: GPT-6 Astra (`gpt-6-astra`), chosen by MK 2026-11-16, replacing an
earlier same-day choice of Claude Opus 5.5. The saved scenarios `gen_seed1.md` and
`gen_seed6.md` were not written by this pipeline: Claude (Sonnet) wrote them from the
specs on 2026-11-16, as their headers state.

Backend rule (MK, 2026-11-16, for replicability): if the user explicitly supplies an
API key for the scenario model, call the API with it. Otherwise, fall back to the Codex
CLI (`codex exec`) on the user's own ChatGPT subscription. MK's runs use the
subscription. The CLI adds its own system prompt and tools, so the two backends are
not identical. Record the backend, model ID, CLI version or API settings, and flags
with each scenario, and save every generated scenario so others can reuse the exact
scenarios without regenerating them.
Record the exact model ID and settings with each generated scenario.

## Interpretation boundaries

Silence or politeness is not agreement. An objection is information, not an automatic
veto. The point person's coordinating role is separate from authority over anyone
else's decision.
