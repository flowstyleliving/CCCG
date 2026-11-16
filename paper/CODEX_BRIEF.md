# Brief for Codex: finish and compile the paper

Work only inside this `paper/` folder. Do not run models, git, or network calls.

1. Read `main.tex`, every file in `sections/`, `results/*.tex`, `results/summary.json`,
   `figures/HAB_FIGURES.md`, and `../scenarios/family_will.md`.
2. Fill the Results section from `results/` only. Every number in the text must appear in
   `results/summary.json` or a `results/*.tex` table. Include `results_table.tex`,
   `effects_table.tex`, `behaviour_table.tex`, and Figures `figures/fig_scores.pdf` and
   `figures/fig_effects.pdf` with captions readable on their own. State n per cell, that
   intervals are bootstrap over episodes, and that the baseline is the neutral + placebo arm.
   Put `checks_table.tex` in the appendix.
3. Write the abstract (150-250 words) last, from the actual results. Also save it as plain
   text in `abstract.txt`.
4. Keep the required sections: Introduction; Related Work; Methodology; Results; Discussion
   (implications, limitations, future work); Limitations and Dual-Use / Ethical
   Considerations; References; Appendix. Main text 4-8 pages, references and appendix not
   counted. Short, plain sentences. Do not claim significance where intervals cross zero.
5. Keep these facts: CCCG was started earlier (Oct 31, 2026) as a hospital-discharge
   simulator; this pilot started anew, keeping only the principles. Cite Kashtan (HCD) for
   CF, Fiasco as the simulator inspiration, and Mackenzie & Stoljar for relational
   autonomy. Label our adaptations as ours. The rubric (18 checks) is ours and was not
   reviewed by a human; one LLM judge (Nemotron 3 Ultra) scored it; no human check was done.
6. Compile with `tectonic main.tex` and fix errors until `main.pdf` builds. Report the page
   count of the main text.
