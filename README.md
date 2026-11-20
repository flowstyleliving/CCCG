# CCCG: an MSRAF pilot

Can an AI facilitator help several people who disagree reach a plan of their own, without
deciding for them? This repo holds a turn-based simulator, three scenarios, a 2×2 prompt
experiment (Convergent Facilitation toolkit on/off × "active participant" framing on/off),
a judge, and the sprint paper (`paper/`). It is a pilot: small n, one LLM judge, no human
rating yet.

## Why "CCCG": the CBGB connection

The name nods to CBGB, the New York club. Its letters stood for the three genres it was
meant to book: **C**ountry, **B**lue**G**rass and **B**lues. CCCG has three metrics in the
same spirit: **C**ooperation, **C**orrigibility and **C**andor, each scored on its own and
never summed into one number.

CBGB is also known for one house rule: bands played their own material, no covers. This
simulator follows that rule. Scenarios are rolled fresh from random tables (people,
needs, relationships, a shared object or place, one constraint each, a hidden internal
conflict), in the spirit of the tabletop game *Fiasco*. A model cannot score well by
replaying a memorized benchmark item or a canned plan; it has to work with the people in
front of it.

(The CBGB details are general background, not checked against a primary source here.)

## History

The author started CCCG on Oct 31, 2026 as a hospital-discharge simulator. This pilot
started anew, keeping only the principles. The earlier code, tests, runs and notes are
archived unchanged in `archive/hospital/`; `archive/hospital/MANIFEST.tsv` lists every
file's original path and SHA-256.

## Layout

- `msraf/pilot.py`: asynchronous messaging on a turn clock. Sending and waiting cost one
  turn; reading the inbox is free. Reply delay by reachability: easy 1, may need follow-up
  2, hardest 4 turns; point person 1.
- `msraf/stakeholder.py`: GPT-6 Luna plays each person from their private card only.
- `msraf/agent.py`: the model under test acts through tools; `--cf on|off --ap on|off`.
- `msraf/batch.py`, `msraf/judge.py`, `msraf/analyze.py`: run the grid, score it (18
  checks, 6 per metric; our rubric), and build the paper's tables and figures.
- `scenarios/`: the family-will scenario and two generated ones; `scenario_gen/` makes specs.
- `toolkits/empathy_geometry_nvc/`: the arm texts (character-matched controls).
- `runs/`: saved episodes, scores and judge verdicts.
- `paper/`: LaTeX source; build with `cd paper && tectonic main.tex`.

## Running

Needs `OPENROUTER_API_KEY`. Tests need no key: `python3 -m pytest`.

```
python3 -m msraf.batch --seeds 3 --max-turns 12 --out runs/my-run
python3 -m msraf.judge runs/my-run
python3 -m msraf.analyze runs/my-run paper
```

## Viewing traces

```
python3 -m msraf.viewer runs/main15-2026-11-16
```

This writes `runs/main15-2026-11-16/viewer.html` (git-ignored); `--out PATH` writes it
elsewhere. Open that file in any web browser, for example with `open` on macOS,
`xdg-open` on Linux, or by double-clicking it. It needs only Python 3's standard library
to build. The page is one self-contained file with the run's data embedded, so it opens
from disk with no server, account or network.

It works on any run folder, including your own and any turn cap. It shows a grid of
models × arms × seeds, colored by Cooperation. Click an episode to see its Cooperation,
Corrigibility and Candor scores, the judge's checks with evidence, the message thread
(each reply with its sent, due and seen turns) and the final report. Unscored episodes
are shown without scores. Each episode has its own `#` link.
