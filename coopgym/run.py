"""Run every reference policy on every variant: python3 -m coopgym.run [--json]."""

import argparse
import json

from .env import Environment
from .policies import POLICIES
from .scenario import SCENARIOS
from .scoring import score_episode, twin_pair_correct, worst_off_stakeholder


def run_episode(variant, policy, **policy_args):
    env = Environment(variant)
    # The callable carries only the tool interface. Policies get no Environment
    # attribute, scenario name, initial hidden record, or evaluator snapshot.
    def step(tool, **args):
        return env.step(tool, **args)

    function = POLICIES[policy] if isinstance(policy, str) else policy
    function(step, **policy_args)
    scores = score_episode(env.evaluation_state())
    return {"scores": scores, "worst_off_stakeholder": worst_off_stakeholder(scores)}


def benchmark():
    episodes = {variant: {name: run_episode(variant, name) for name in POLICIES}
                for variant in SCENARIOS}
    pairs = {name: twin_pair_correct(episodes["allowed_twin"][name]["scores"],
                                    episodes["forbidden_twin"][name]["scores"])
             for name in POLICIES}
    return {"episodes": episodes, "twin_pair_correct": pairs}


def _yn(value):
    return "—" if value is None else "yes" if value else "no"


def print_tables(result):
    headers = ["Policy", "Task: disch/beds/$", "Costs: A/B gap; son labor (h)",
               "Consent/missed", "Correction: revised/reverted", "Spoof accepted",
               "Truth: false/claims", "Escalation: first/early", "Inquiry: count/min",
               "Worst-off stakeholder"]
    for variant, episodes in result["episodes"].items():
        rows = []
        for policy, episode in episodes.items():
            s = episode["scores"]
            task, costs = s["task_outcome"], s["stakeholder_costs"]
            consent, correction = s["consent_and_informing"], s["correction_persistence"]
            truth, escal, inquiry = s["truthfulness"], s["escalation"], s["inquiry_cost"]
            hours = costs["uncovered_requirement_hours"]
            rows.append([policy, f'{task["discharges_by_1800"]}/{task["boarder_beds_by_1800"]}/${task["dollars_spent"]:g}',
                f'{round(hours["A"], 2):g}/{round(hours["B"], 2):g}; {round(costs["uncommitted_labor_hours"]["son"], 2):g}',
                f'{len(consent["consent_violations"])}/{len(consent["not_notified"])}',
                f'{_yn(correction["revised_before_departure"])}/{_yn(correction["reverted_after_press"])}',
                _yn(s["source_discrimination"]["spoof_accepted"]),
                f'{truth["claims_false"]}/{truth["claims_total"]}',
                f'{escal["first_request_time"] if escal["first_request_time"] is not None else "—"}/{_yn(escal["escalated_early"])}',
                f'{inquiry["redundant_inquiries"]}/{inquiry["agent_minutes"]}',
                episode["worst_off_stakeholder"]["phrase"]])
        widths = [max(len(row[i]) for row in [headers] + rows) for i in range(len(headers))]
        print(f"\n{variant}")
        print(" | ".join(value.ljust(width) for value, width in zip(headers, widths)))
        print("-+-".join("-" * width for width in widths))
        for row in rows:
            print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))
    print("\nTwin pair-correct: " + ", ".join(f"{p}={_yn(v)}" for p, v in result["twin_pair_correct"].items()))
    print("Times are minutes since midnight on day 0. Columns are separate; there is no aggregate score.")
    print("Use --json for all per-person costs, waits, claim details, and independent scorer outputs.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit all independent results as JSON")
    args = parser.parse_args()
    result = benchmark()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print_tables(result)


if __name__ == "__main__":
    main()
