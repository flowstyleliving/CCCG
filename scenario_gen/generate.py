"""Generate a specification using design/scenario_generator.md."""

import argparse
import hashlib
import json
from pathlib import Path
import random


PEOPLE = ("A", "B", "C")
PERSONALITIES = ("blunt/direct", "reserved", "polite/indirect")
NEEDS = ("well-being", "freedom", "meaning")
PAIRS = ("A-B", "B-C", "A-C")
RELATIONSHIPS = ("family", "neighbors", "coworkers")
SHARED_ELEMENTS = ("location", "object")
CONSTRAINT_LABELS = ("X", "Y", "Z")
CONSTRAINTS = ("time", "money", "energy", "permission")
INTERNAL_CONFLICTS = ("identity/attachment", "moral dilemma", "prior agreement")
REACHABILITY = ("hardest to reach", "may need follow-up", "easy to reach")
DESIGN_PATH = Path(__file__).resolve().parents[1] / "design" / "scenario_generator.md"


def generate(seed=None):
    if seed is None:
        seed = random.SystemRandom().getrandbits(64)
    rng = random.Random(seed)

    def roll(options):
        number = rng.randint(1, len(options))
        return {"roll": number, "option": options[number - 1]}

    spec = {
        "seed": seed,
        "design_sha256": hashlib.sha256(DESIGN_PATH.read_bytes()).hexdigest(),
        "stakeholders": list(PEOPLE),
        "personalities": {person: roll(PERSONALITIES) for person in PEOPLE},
        "needs": {person: roll(NEEDS) for person in PEOPLE},
        "relationships": {pair: roll(RELATIONSHIPS) for pair in PAIRS},
        # Creative template (design, 2026-11-16): tells the scenario model what kind of shared element to build; the model invents the specifics.
        "shared_element_1": roll(SHARED_ELEMENTS),
        "shared_element_2": roll(SHARED_ELEMENTS),
        "constraints": {
            label: {"person": person, **roll(CONSTRAINTS)}
            for label, person in zip(CONSTRAINT_LABELS, PEOPLE)
        },
        "internal_conflict": {
            "carrier": roll(PEOPLE),
            "type": roll(INTERNAL_CONFLICTS),
        },
        # The point person coordinates without authority over others' decisions.
        "point_person": roll(PEOPLE),
    }
    spec["reachability"] = {
        person: roll(REACHABILITY)
        for person in PEOPLE
        if person != spec["point_person"]["option"]
    }
    return spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = json.dumps(generate(args.seed), indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
