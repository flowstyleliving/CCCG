import random
import unittest

from scenario_gen.generate import generate


class GenerateTest(unittest.TestCase):
    def test_spec(self):
        people = ("A", "B", "C")
        for seed in range(100):
            with self.subTest(seed=seed):
                spec = generate(seed)
                self.assertEqual(spec, generate(seed))
                self.assertEqual(spec["seed"], seed)
                self.assertEqual(spec["stakeholders"], list(people))
                rng = random.Random(seed)

                def check_roll(record, options):
                    number = rng.randint(1, len(options))
                    self.assertEqual(record["roll"], number)
                    self.assertEqual(record["option"], options[number - 1])

                for field, keys, options in (
                    ("personalities", people, ("blunt/direct", "reserved", "polite/indirect")),
                    ("needs", people, ("well-being", "freedom", "meaning")),
                    ("relationships", ("A-B", "B-C", "A-C"), ("family", "neighbors", "coworkers")),
                ):
                    self.assertEqual(list(spec[field]), list(keys))
                    for key in keys:
                        check_roll(spec[field][key], options)
                for field in ("shared_element_1", "shared_element_2"):
                    check_roll(spec[field], ("location", "object"))
                self.assertEqual(list(spec["constraints"]), ["X", "Y", "Z"])
                for label, person in zip(("X", "Y", "Z"), people):
                    record = spec["constraints"][label]
                    self.assertEqual(record["person"], person)
                    check_roll(record, ("time", "money", "energy", "permission"))
                check_roll(spec["internal_conflict"]["carrier"], people)
                check_roll(spec["internal_conflict"]["type"],
                           ("identity/attachment", "moral dilemma", "prior agreement"))
                check_roll(spec["point_person"], people)
                remaining = [p for p in people if p != spec["point_person"]["option"]]
                self.assertEqual(list(spec["reachability"]), remaining)
                for person in remaining:
                    check_roll(spec["reachability"][person],
                               ("hardest to reach", "may need follow-up", "easy to reach"))


if __name__ == "__main__":
    unittest.main()
