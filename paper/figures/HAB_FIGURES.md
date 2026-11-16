# HumanAgencyBench (HAB) figures and tables

Source: Sturgeon, Samuelson, Haimes, Anthis. "HumanAgencyBench: Scalable Evaluation of Human Agency Support in AI Assistants." arXiv 2509.08494 (v2 HTML, read 2026-11-16).
Figures 1 and 4 were inspected as images. Figures 2 and 3 and Tables A1 to A6 come from the HTML text and captions only (Fig. 3 is an SVG not viewed).
Behaviors: Ask Clarifying Questions (ACQ), Avoid Value Manipulation (AVM), Correct Misinformation (CM), Defer Important Decisions (DID), Encourage Learning (EL), Maintain Social Boundaries (MSB).

## Figures

| # | Chart type | Axes | Grouping | Variance |
|---|-----------|------|----------|----------|
| 1 (`mainfig.png`) | Six small horizontal bar-chart panels in a 2x3 grid, one per behavior. Each panel has a bold title and the one-line question it tests on the left. | y: 5 models (GPT-5 Thinking, Claude 4.1 Opus, Gemini 2.5 Pro, Grok 4, Llama 4 Maverick). x: score, 0 to 1, ticks at 0, 0.25, 0.5, 0.75, 1. | Panels = behaviors. Bars inside a panel = one flagship model per developer. Alternating grey backgrounds separate panel pairs. Bar fill is a viridis gradient that also encodes the value (long bar = green). | Standard-error whiskers on every bar (caption: "Error bars represent standard errors"). Light dashed vertical gridlines. |
| 2 (`examples.png`) | Annotated text figure (not a data chart). Shows one simulated user query, the grading rubric and two model responses. | None. | Color blocks: query blue, rubric purple, Claude-3.5-Sonnet response green, Claude-3-Haiku response orange. Scores are deductions from a maximum of 10. | None. |
| 3 (`pipeline.svg`) | Pipeline / flow diagram of test generation (simulate, validate, cluster). | None. | Steps in order. | None. |
| 4 (`model_comparison.png`) | Grid of small horizontal bar panels: 6 columns (behaviors) by 5 row groups (developers), 25 models in total (OpenAI 8, Anthropic 8, Google 4, Meta Llama 3, xAI 2). Behavior names sit above the columns, rotated. | y: model names, shown once at the left of each row group. x: score, labeled "Score (Scaled to 0-1)" once at the bottom, same 0 to 1 range in every panel. | Rows = developer, columns = behavior, so one model is read across the row. Same viridis value-gradient fill. Row-group height scales with model count. | Standard-error whiskers on every bar. Dashed gridlines. |

## Tables (appendix)

| # | Content | Rows / columns | Variance |
|---|---------|----------------|----------|
| A1 | The numbers behind Fig. 4. | Rows: 25 models grouped by developer. Columns: release date, six behavior scores, Avg. Best value per column in bold. | None. |
| A2 | Diversity of the 500 tests per behavior (mean pairwise cosine similarity, 95th percentile, number of clusters, cluster entropy). | Rows: six behaviors. | None (a distribution summary only). |
| A3 | Judge agreement: Spearman correlation of o3's model ranking with Gemini-2.5-Pro, Claude-4-Sonnet and GPT-4.1 rankings. | Rows: six behaviors plus Overall. Columns: three comparison judges. | 95% CIs from 2,000 prompt-level bootstrap replicates, in brackets. |
| A4 | Subjective 0 to 10 relevance of six agency theories to the six behaviors. | Rows: theories. Columns: behaviors. | None. |
| A5 | Mean HAB score (percent) by system-prompt condition (Default, Helpful, Autonomy, Direct) plus the Autonomy minus Direct gap. | Rows: nine 2026 checkpoints. | None. |
| A6 | Autonomy minus Direct gap per behavior, in percentage points. | Rows: nine models plus Mean. Columns: six behaviors. | None. |

Notes for our use:
- HAB has no summed score in the figures. Table A1 does carry an "Avg" column. We should not add one.
- The text reports scores both as 0 to 1 (Fig. 1, 4) and as percent (Section 4, Tables A5, A6). Pick one. Our metrics are 0 to 1.

## Recommendation for our charts

We have 4 models x 4 arms x 3 metrics (Cooperation, Corrigibility, Candor; each a share of checks passed, 0 to 1).
1. Mirror Fig. 1 and Fig. 4: one small horizontal-bar panel per metric (3 panels in a row), a shared 0 to 1 x-axis, models on the y-axis, and standard-error or bootstrap-CI whiskers on every bar. Do not sum the metrics and do not draw an average panel.
2. Inside each model, draw the 4 arms as 4 adjacent bars. Encode CF by hue and AP by lightness or hatching, so the 2x2 reads at a glance. Do not reuse HAB's value-gradient fill, because color has to carry the arm here.
3. Optional second figure: an interaction plot per metric (x: CF off to on, one line per AP level, one panel per model) to show main effects and interaction directly. Put the matching numbers in a table as HAB does in Table A1, with the best value per column in bold.
