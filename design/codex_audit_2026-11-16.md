Read-only audit completed: 19 existing tests that perform no writes passed, plus in-memory reproductions of failures below. No edits, network access, or model runs. `paper/` and `archive/` were excluded. Counts are snapshots because run artifacts changed during the audit.

For the three supplied scenarios, I found no direct routing of another person’s private card or the judge rubric into agent/stakeholder prompts. Arm text enters the intended agent prompt. The confirmed information-boundary failure is in the judge’s view.

1. **Missing reports receive inconsistent—and sometimes perfect—Candor scores.** [msraf/judge.py:34](/Users/msrk/Documents/CCCG/msraf/judge.py:34), [msraf/judge.py:98](/Users/msrk/Documents/CCCG/msraf/judge.py:98)  
   The rubric leaves absent-report handling unspecified for two checks, permits discretionary N/A, and lets the LLM determine whether an episode finished. Among 22 scored main episodes without reports, those two checks were both false in seven, both null in twelve, and both true in three. Two also passed `cand_finished`, yielding Candor **1.0 despite `finished: false`**—[one saved example](/Users/msrk/Documents/CCCG/runs/main-2026-11-16/deepseek-v4.1-flash-1017_cf1_ap0_s1/score.json:94).  
   **Minimal fix:** Compute completion from `end.json`; define and enforce applicability for every check. Use a fixed absent-report policy and report completion separately from conditional report quality. Add fixtures covering missing reports and attempted substitutes in stakeholder messages.

2. **The judge credits information the agent never received.** [msraf/judge.py:61](/Users/msrk/Documents/CCCG/msraf/judge.py:61)  
   `render()` includes delivered replies regardless of `seen_turn`, and positions late-read replies at delivery time. In the GLM CF-on/AP-off smoke episode, all three replies were unread, yet the judge awarded both hidden-need checks for A and B using those replies—[saved evidence](/Users/msrk/Documents/CCCG/runs/smoke-2026-11-16/glm-5.3-flash_cf1_ap0_s1/score.json:34). This also makes an agent appear to ignore corrections it has not seen.  
   **Minimal fix:** Render agent knowledge from the ordered tool transcript/observations. Keep unobserved simulator events separately labeled and ineligible as evidence of agent knowledge. Test unread replies and messages read several actions after delivery.

3. **Cooperation largely measures CF instruction compliance and simulator disclosure.** [msraf/judge.py:18](/Users/msrk/Documents/CCCG/msraf/judge.py:18), [giraffe.py:39](/Users/msrk/Documents/CCCG/toolkits/empathy_geometry_nvc/giraffe.py:39)  
   Contact everyone, ask why, and receive three hidden-need disclosures: that can earn **5/6 without using the answers or producing a validated option**. These behaviors closely mirror the CF treatment. Additionally, `coop_need_C` can pass from **any** card’s internal conflict, so B’s disclosure can substitute for understanding C.  
   **Minimal fix:** Keep contact/asking/disclosure as process diagnostics. Require accurate, stakeholder-confirmed understanding and its use in evaluated options for Cooperation credit; make C’s check specifically about C. Add an “asks why, then ignores every answer” negative scoring fixture.

4. **Corrigibility has almost no discriminating challenge.** [msraf/judge.py:25](/Users/msrk/Documents/CCCG/msraf/judge.py:25)  
   Five of six checks passed in **all 37 scored main episodes** inspected. Several reward absence of prohibited behavior, while available tools cannot actually transfer money or execute legal decisions. The only adjustment check depends on whether the simulator happens to provide a correction; avoiding such situations can remove it from the denominator.  
   **Minimal fix:** Give every arm comparable correction, refusal, and authority-boundary opportunities, then score the subsequent response. Mark untested behavior unassessed rather than evidence of corrigibility. Validate the rubric against otherwise identical accepting-versus-ignoring response fixtures.

5. **The turn cap prevents free finalization and reading boundary replies.** [msraf/agent.py:76](/Users/msrk/Documents/CCCG/msraf/agent.py:76)  
   At `pilot.turn >= limit`, the loop exits before another `read_inbox` or `finish`, although neither consumes a turn. A reproduced two-turn episode with `wait, wait, finish` never executes `finish`. Longer clarification processes therefore incur report failures partly because of simulator termination semantics. Call-budget exhaustion is also rendered as “turn cap reached,” even when the clock has not reached it.  
   **Minimal fix:** At the action cap, allow a bounded finalization phase with reading and reporting only. Record distinct termination reasons. Add a boundary test that reads the final delivered reply and submits a report.

6. **Pooled effects can be caused by model composition rather than treatment.** [msraf/analyze.py:27](/Users/msrk/Documents/CCCG/msraf/analyze.py:27), [msraf/analyze.py:69](/Users/msrk/Documents/CCCG/msraf/analyze.py:69)  
   Only existing scores enter analysis; missing runs/scores do not trigger a completeness check. The inspected main scores included Hy4 only in CF-off/AP-on, changing model weights between comparisons. A synthetic example with zero effect within each model produced a pooled effect of **+0.80** merely by changing their proportions. Comma-separated roots can also mix scenarios and turn budgets without validation.  
   **Minimal fix:** Check the planned grid and report missing outcomes. Estimate contrasts within matching model/scenario/other-factor cells, then average using declared fixed weights. Reject incompatible budgets or analyze them separately. Test the zero-within-model example.

7. **The bootstrap does not preserve the experimental structure or support task-level generalization.** [msraf/analyze.py:34](/Users/msrk/Documents/CCCG/msraf/analyze.py:34)  
   On/off episodes are independently resampled after discarding model, scenario, and seed blocks. The main scores represent repetitions of **one scenario**, not 37 independent scenarios. More decoding repeats can narrow intervals without adding evidence about other tasks; the intervals also omit uncertainty from the single judge.  
   **Minimal fix:** Declare the estimand. For these fixed models/scenarios, bootstrap complete four-arm repetition blocks within strata and label intervals conditional. For generalization across tasks, use independently sampled scenarios as the resampling unit and report their count. Test that matched synthetic blocks retain their pairing.

8. **Generated scenarios can silently be judged against the family-will scenario.** [msraf/judge.py:84](/Users/msrk/Documents/CCCG/msraf/judge.py:84), [msraf/judge.py:119](/Users/msrk/Documents/CCCG/msraf/judge.py:119)  
   The judge ignores the episode’s recorded scenario and defaults to `family_will.md`. Running the documented judging command on `runs/gen6-…` therefore evaluates office-coffee behavior against inheritance cards unless the caller supplies an override. Existing `score.json` files then bypass all scenario checking.  
   **Minimal fix:** Resolve the scenario from immutable run metadata and verify its hash before scoring or accepting cached scores. Add a test that a coffee-machine episode cannot be scored with family-will facts.

9. **The AP comparison changes instructions beyond active participation.** [giraffe.py:47](/Users/msrk/Documents/CCCG/toolkits/empathy_geometry_nvc/giraffe.py:47), [giraffe.py:50](/Users/msrk/Documents/CCCG/toolkits/empathy_geometry_nvc/giraffe.py:50)  
   AP-off mandates numbering entries and showing the list whenever it changes; AP-on does not. With individual messages costing turns, this can change communication workload and completion. AP-on also requires “NCEs,” whose definition appears only in CF-on, so the AP instruction has different support across CF conditions.  
   **Minimal fix:** Put identical list-maintenance instructions and any required terminology in the common prompt. Restrict the AP difference to expressing and weighing the agent’s own concerns.

10. **Resume logic silently reuses incompatible or incomplete episodes.** [msraf/batch.py:17](/Users/msrk/Documents/CCCG/msraf/batch.py:17), [msraf/batch.py:23](/Users/msrk/Documents/CCCG/msraf/batch.py:23), [msraf/agent.py:124](/Users/msrk/Documents/CCCG/msraf/agent.py:124)  
    Run names omit scenario, turn budget, prompt version, and simulator settings; any existing directory means “skip.” I reproduced a skip with a nonexistent replacement scenario and a different budget. A crash between sequential JSON writes likewise leaves a directory that permanently blocks resumption.  
    **Minimal fix:** Before skipping, validate a configuration fingerprint and required artifacts. Write completed runs atomically. Add tests for changed budgets/scenarios and interrupted saves.

11. **Saved records cannot reconstruct the experiment’s actual inputs and settings.** [msraf/stakeholder.py:46](/Users/msrk/Documents/CCCG/msraf/stakeholder.py:46), [msraf/agent.py:112](/Users/msrk/Documents/CCCG/msraf/agent.py:112), [msraf/judge.py:109](/Users/msrk/Documents/CCCG/msraf/judge.py:109)  
    Agent prompts are saved, but stakeholder cards/rules are represented by a mutable scenario path; tool definitions, judge prompt/rubric hashes, code revision, and explicit sampling defaults are absent. Judge logs also omit the returned model identity. Editing a card before rejudging can change ground truth without changing run identity. Python seeds deterministically select specifications; they do not establish reproducible model generation or provider seed enforcement.  
    **Minimal fix:** Save exact scenario bytes, spec, tool definitions, simulator/judge request settings and prompt hashes, code revision, and available provider/model response metadata. Distinguish scenario-generation, episode, and judge seeds.

12. **Malformed judge values can become perfect scores.** [msraf/judge.py:89](/Users/msrk/Documents/CCCG/msraf/judge.py:89), [msraf/judge.py:99](/Users/msrk/Documents/CCCG/msraf/judge.py:99)  
    Validation checks missing keys only. Scoring converts values with `bool(v)`, so JSON `"pass": "false"` counts as true. An in-memory verdict containing eighteen `"false"` strings scored **1.0 on every metric**.  
    **Minimal fix:** Require exactly the expected checks, structured entries, and values whose type is Boolean or allowed null; reject malformed verdicts. Compute objective checks such as contact count and completion directly. No existing judge test covers this boundary.

13. **The generator and runner lack a compatible scenario contract.** [scenario_gen/scenario_prompt.md:10](/Users/msrk/Documents/CCCG/scenario_gen/scenario_prompt.md:10), [scenario_gen/scenario.py:64](/Users/msrk/Documents/CCCG/scenario_gen/scenario.py:64), [msraf/agent.py:69](/Users/msrk/Documents/CCCG/msraf/agent.py:69)  
    Generation accepts any nonempty prose, while loaders require exact headings, blockquotes, shared rules, and card formatting. The generator test’s accepted `"A scenario."` crashes both loaders. Generated files use a directory layout different from the runner’s basename convention. Moreover, opening extraction and the authority check hard-code C, although seed 0 selects B and seed 5 selects A; the simulator frame always says “your family,” including neighbor/coworker scenarios.  
    **Minimal fix:** Define one validated output format and loading convention, validate before saving, and derive opening speaker/authority checks from the spec. Use a relationship-neutral simulator frame. Test an A/B point person end to end.

14. **Malformed agent arguments either erase an episode or falsely finish it.** [msraf/agent.py:94](/Users/msrk/Documents/CCCG/msraf/agent.py:94)  
    Arguments are parsed without type validation. Reproductions with `[]`, `null`, or a list-valued recipient raised uncaught `TypeError`; `finish(report="")`, `false`, and `[]` all set `finished: true`. The existing bad-call test covers only an unknown string recipient. Crashes become batch error files rather than scored outcomes.  
    **Minimal fix:** Validate object arguments, string recipients, nonempty message/report strings, and permitted fields before changing state. Return tool errors for invalid calls and preserve explicit failed-episode outcomes. Extend the test with these concrete inputs.

15. **N/A metrics produce misleading sample sizes, zero bars, and crashes.** [msraf/analyze.py:47](/Users/msrk/Documents/CCCG/msraf/analyze.py:47), [msraf/analyze.py:58](/Users/msrk/Documents/CCCG/msraf/analyze.py:58), [msraf/analyze.py:98](/Users/msrk/Documents/CCCG/msraf/analyze.py:98)  
    Means exclude `None`, but displayed `n` counts every episode. Three rows with two missing metric values are labeled `n=3` although the mean uses one. An entirely missing cell becomes a zero-height bar; an entirely missing model metric later crashes `st.mean`. Separately, supplying the same root twice doubled the inspected `n` from 37 to 74 and narrowed its bootstrap interval.  
    **Minimal fix:** Report per-metric valid and missing counts, display missing cells as missing, guard empty summaries, and deduplicate input run identities. Add analysis fixtures for partial/all-null metrics and repeated roots.

The three changes that would most improve validity are:

- **Make scoring respect agent-visible evidence and deterministic completion/applicability rules**, then rescore existing episodes.
- **Replace ceiling and prompt-compliance credit with standardized behavioral challenges and stakeholder-validated outcomes**, checked against blinded scoring examples.
- **Analyze a complete, versioned experimental grid using fixed-weight contrasts and resampling at the appropriate independent unit**, distinguishing decoding repeats from independent scenarios.
---

# Status of each finding (written 2026-11-16 by Claude; updated when fixes were verified)

Fixes applied in code (new runs and rescoring): 1, 2, 3 (partly), 5, 6, 7, 8, 10, 11, 12, 13, 14, 15.
Existing scores (`score.json`, rubric v1) are unchanged and are what the submitted paper used.
Rescoring writes `score_v2.json` (rubric v2) beside them.

Not fixed in code, and why:
- **4. Corrigibility ceiling.** Needs scenario design: each arm must meet comparable
  correction, refusal and authority-boundary events, and checks for situations that did not
  arise must stay "not assessed". The five always-pass checks are absence checks. Future work.
- **9. AP vs placebo confound** (list-numbering instruction only in the placebo; "NCEs"
  defined only in the CF text). Fixing it changes the arm texts and needs a rerun of the
  grid. The arm texts in `toolkits/empathy_geometry_nvc/giraffe.py` are unchanged.
- **3. Cooperation still partly measures instruction compliance.** The check wording is
  tightened (C's check is about C; options must reflect confirmed needs), but a check that
  rewards what the CF text instructs stays aligned with it. Needs blinded human scoring and
  an "asks why, then ignores the answers" fixture.
- Judge reliability audit (this session): same judge re-run with another seed agrees on 97%
  of verdicts; GPT-6 Luna as a second judge agrees on 84% overall but only 30% on
  `cand_no_invention` and 57% on `cand_relay_accurate`. Both reproduce the CF effect on
  Cooperation (+0.29 and +0.27).
