You are building v0 of a benchmark simulator in this folder (~/Documents/cooperation-gym).

Read these first, in full:
- design/refined_spec.md  (the spec you implement; it is authoritative)
- README.md               (existing design README; keep its text)
- design/coopgym_flagship.md and design/coopgym_codex_final.md (background only)

Implement exactly what design/refined_spec.md describes:
- Python 3.11, standard library only, unittest. Package `coopgym/` (scenario definitions incl. all five variants, env with the uniform `env.step(tool, **args)` interface, clock and events, commitment/consent ledgers that only the env can write, the separate scorers, worst-off-stakeholder reporting, twin pair-correct, and the seven reference policies) and `tests/`.
- Policies must only use tool results; they must never read the variant name or hidden ground truth.
- Scorers must never read free text and must not emit any total, weighted, or aggregate score.
- Demo: `python3 -m coopgym.run` prints one table per variant (row per policy, scorer columns, worst-off stakeholder) and `--json` prints machine-readable output.
- Tests: every expected separation in spec section 8, plus determinism, no-credit-for-words, no-aggregate, and no-leakage tests.
- README.md: keep all existing text, change only the Status block so it no longer says no code exists, and add a section for the v0 simulator with run commands, test commands, and the honest limits from spec section 10. If you had to deviate from the spec anywhere (for example an internal inconsistency), add a short "Deviations from spec" list to that README section.

Rules: do not use the network, do not add dependencies, do not run git commit or push, do not modify files under design/ other than reading them. Run `python3 -m unittest discover -s tests -v` and `python3 -m coopgym.run` yourself before finishing and make all tests pass. Finish with a short summary: files created, test count and result, and any deviations.
