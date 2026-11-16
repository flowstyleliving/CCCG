# Empathy Geometry giraffe (NVC) frame — vendored copy

A self-contained copy of the giraffe (NVC) conversation frame from the Empathy
Geometry study, for use in CCCG toolkit-vs-baseline runs. Nothing in this folder
reads from the original directories. `msraf/agent.py` imports only the four
`*_DRAFT` arm texts; `NVC_CF_TOOLKIT` is not used in runs yet.

## Contents

- `giraffe.py`:
  - `GIRAFFE_FRAME` — exact Empathy Geometry text, hash-locked by
    `GIRAFFE_FRAME_SHA256` (assert at import). Unchanged since the copy.
  - `CF_STEPS` — four facilitation steps added 2026-11-15 (see below).
  - `TRUST_PACING` — pacing addendum added 2026-11-15 (see below).
  - Unused draft placeholders for the planned 2×2 (CF toolkit on/off × active
    participant on/off), none in `NVC_CF_TOOLKIT` or its hash:
    - `CF_COMPACT_DRAFT` (870 chars): compact CF toolkit, including "easy to say
      no" (lowering the threshold, HCD pp. 191, 231) and trust-paced checking
      (pp. 196, 269). Would replace the giraffe frame, `CF_STEPS` and `TRUST_PACING`.
    - `CF_NEUTRAL_DRAFT` (870 chars): style-only control for the CF factor.
    - `AP_DRAFT` (326 chars): active-participant treatment ("no more and no less",
      p. 255), our extension to an AI agent.
    - `AP_PLACEBO_DRAFT` (326 chars): role-only control for the AP factor.
    Lengths are character-matched exactly (controls padded 2026-11-16, MK: char count for
    now); token-match with the run model's tokenizer later. Wired as arms in `msraf/agent.py`.
  - `NVC_CF_TOOLKIT` — `GIRAFFE_FRAME + "\n\n" + CF_STEPS + "\n\n" + TRUST_PACING`,
    the one combined toolkit text for runs, hash-locked by `NVC_CF_TOOLKIT_SHA256`
    (`8156164f395d29ba09ee05080a13f292c5933d7ded096102072fd425c0d39230`; the
    pre-addendum hash was `9aadddd2…`).
  - `compose_system(persona_profile, shared_event, frame=NVC_CF_TOOLKIT)` — Empathy
    Geometry's system-message layout. `frame=GIRAFFE_FRAME` reproduces the original
    message exactly.

## CF steps: a CCCG adaptation

`CF_STEPS` is a CCCG condensation of Convergent Facilitation, **not Kashtan's
verbatim protocol**. Grounding (printed pages of *The Highest Common Denominator*,
2020): asking for the "why" (p. 151), the two translation moves (pp. 151–152),
checking with the speaker and the essence checklist (p. 153), and giving a proposal
that misses a criterion back for revision (p. 175).

Sequence MK specified: collect needs first (no initial plan), distill them into
criteria each stakeholder confirms, then the agent drafts solutions that meet those
criteria and returns them for stakeholder validation. Unconfirmed summaries,
silence, or disagreement never count as agreement; objections are kept as needs;
nobody is pressed to agree.

## Trust pacing: a CCCG adaptation

`TRUST_PACING` puts the principle "move at the speed of trust" into operational
terms, as MK requested. The wording is ours, not a verified source quotation; the
phrase's origin was not checked. It paces needs clarification and proposal
validation to readiness people express, and allows questions, uncertainty, pauses
and refusal. It also says silence is not agreement and a turn limit is no reason to
rush. It does not claim the agent can read inner trust, and it does not require
waiting forever: a concern that cannot be resolved within practical limits is
recorded as unresolved.

## Design note: arms (not implemented)

MK, 2026-11-15: "the two arms be CF toolkit and an active participant." This
toolkit is the CF arm: one combined NVC+CF text, with no separate NVC-only arm. The
arms are now wired in `msraf/agent.py` from the drafts above (2026-11-16). No runner, arm assignment, scoring, or
turn cap has been changed.

## Provenance (copied 2026-11-15)

- Code source: `/Users/msrk/Documents/empathy-geometry-harness/eg_harness/spec.py`,
  `ARM_BLOCKS["giraffe"]` (line 344), at harness commit
  `3cc7a20b93a43c2b66d24055956de6b494c02f7f`; `spec.py` clean in the working tree,
  last changed in `d031d96` (2026-08-10).
- Design source: `/Users/msrk/Documents/the_GOAT/wiki/empathy-geometry/arm-blocks.md`,
  "## Giraffe" quote. Byte-identical to the code string at copy time.
- SHA-256 (UTF-8): `61a7acb4632541decab5b06cfc0114497b4d5d6708360852c0d74ee86006c4f2`,
  510 characters. Matches the hash the harness stamps as `arm_sha256`
  (`runner.py:103`, `hashlib.sha256(text.encode("utf-8"))`).
- Status upstream: substance approved 2026-07-13; the exact-token matching gate
  (arms within 2 Qwen2.5-7B tokens) was still pending executor verification.

## How Empathy Geometry delivers it

Verified in `eg_harness/providers.py:514` (`build_prompt`): one **system** message
containing persona profile → `Shared event:` → `Conversation frame:` + the arm
block → length rules. Prior turns follow as alternating user/assistant messages,
and a final user message says "You are in conversation with the person in front of
you. This is turn N. Write your next turn." Rendered through the model's own chat
template. No Markdown loading and no file-read tool at run time.

## Design constraints carried over (from arm-blocks.md)

- Same communicative task in every arm; only the frame changes.
- No proposed solution, outcome prediction, arm name, research language, or
  instruction to end in agreement.
- Model-facing text is the frame string only; headings and notes never enter context.
- Arms should be token-matched, so a fair baseline uses a length-matched neutral
  frame in the same slot rather than an empty one. Upstream's matched neutral and
  jackal frames were **not** copied here.

## Fit to MSRAF (not yet decided)

The frame was written for a two-party peer dyad. MSRAF is a facilitator agent with
a patient, a caregiver son, and a care team, so wording such as "the other person"
may need adapting. Any adaptation is a new frame with a new hash, not this one.
