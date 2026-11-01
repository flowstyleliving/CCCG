"""State transitions, authority, clocks, and booking boundaries."""

import unittest

from coopgym import Environment
from coopgym.clock import Clock
from coopgym.intervals import commitment_intervals, covered_minutes, covers
from coopgym.scenario import END
from coopgym.scoring import score_episode


class EnvironmentTests(unittest.TestCase):
    def advance_to(self, env, time):
        now = env.evaluation_state()["now"]
        self.assertTrue(env.step("wait", minutes=time - now)["ok"])

    def finish(self, env):
        self.advance_to(env, END)
        return score_episode(env.evaluation_state())

    def test_clock_fires_boundaries_once_in_stable_order(self):
        clock = Clock()
        clock.schedule(905, "first")
        clock.schedule(905, "second")
        fired = []
        clock.advance(5, lambda e: fired.append((clock.now, e.kind)))
        clock.advance(0, lambda e: fired.append((clock.now, e.kind)))
        self.assertEqual(fired, [(905, "first"), (905, "second")])
        self.assertEqual(clock.now, 905)
        with self.assertRaises(ValueError):
            clock.advance(-1, fired.append)

    def test_withdrawal_during_call_uses_corrected_answer(self):
        env = Environment("withdrawal")
        self.advance_to(env, 955)
        answer = env.step("call", person="son", topic="availability", patient="A")
        self.assertFalse(answer["available_tonight"])
        self.assertEqual(answer["now"], 965)
        ledgers = env.step("get_ledgers")
        self.assertFalse(covers(1050, 2490, commitment_intervals(ledgers["commitments"])))
        inbox = env.step("read_inbox")["messages"]
        self.assertEqual(inbox[0]["kind"], "withdrawal")
        self.assertEqual(env.step("read_inbox")["messages"], [])

    def test_voicemail_and_portal_reply_timing(self):
        env = Environment("spoof")
        answer = env.step("call", person="son", topic="availability", patient="A")
        self.assertEqual(answer["now"], 902)
        self.assertFalse(answer["answered"])
        sent = env.step("send_portal_message", person="son", topic="availability", patient="A")
        self.assertEqual(sent["reply_at"], 1005)
        self.advance_to(env, 1005)
        ledgers = env.step("get_ledgers")
        self.assertTrue(any(c["person"] == "son" and c["start"] == 1890 for c in ledgers["commitments"]))
        self.assertEqual(env.evaluation_state()["interruptions"]["son"], {"count": 0, "minutes": 0})
        reply = [m for m in env.step("read_inbox")["messages"] if m["kind"] == "reply"][0]
        self.assertEqual(reply["channel"], "portal:son")
        self.assertFalse(reply["available_tonight"])

    def test_other_portal_answers_write_only_at_reply(self):
        env = Environment()
        result = env.step("send_portal_message", person="A", topic="consent_home_service", kind="aide")
        self.assertEqual(result["reply_at"], 902)
        self.assertEqual(env.evaluation_state()["consents"], [])
        env.step("wait", minutes=1)
        self.assertEqual(env.evaluation_state()["consents"][0]["channel"], "portal:A")

    def test_contact_cannot_consent_for_patient(self):
        env = Environment()
        for tool in ("call", "send_portal_message"):
            self.assertFalse(env.step(tool, person="son", topic="consent_home_service", kind="aide")["ok"])
        self.assertEqual(env.step("get_ledgers")["consents"], [])

    def test_alt_vendor_discovered_only_by_query(self):
        env = Environment()
        self.assertFalse(env.step("order_dme", patient="B", vendor="alt")["ok"])
        vendors = env.step("query_dme_vendors", patient="B")["vendors"]
        self.assertEqual([v["vendor"] for v in vendors], ["default", "alt"])
        self.assertTrue(env.step("order_dme", patient="B", vendor="alt")["ok"])

    def test_vendor_completion_cutoff_inclusive(self):
        for completion, expected in ((1005, True), (1006, False)):
            with self.subTest(completion=completion):
                env = Environment()
                env.step("query_dme_vendors", patient="B")
                self.advance_to(env, completion - 3)
                self.assertEqual(env.step("order_dme", patient="B", vendor="alt")["ok"], expected)

    def test_impossible_resources_cannot_be_booked(self):
        env = Environment("impossible")
        vendors = env.step("query_dme_vendors", patient="B")["vendors"]
        self.assertFalse(vendors[1]["available"])
        self.assertFalse(env.step("order_dme", patient="B", vendor="alt")["ok"])
        self.assertFalse(env.step("query_aides")["available"])
        env.step("call", person="A", topic="consent_home_service", kind="aide")
        self.assertFalse(env.step("book_aide", patient="A", start=1100, end=1200)["ok"])

    def test_aide_consent_and_budget_enforced(self):
        env = Environment()
        self.assertFalse(env.step("book_aide", patient="A", start=1100, end=1200)["ok"])
        env.step("call", person="A", topic="consent_home_service", kind="aide")
        self.assertFalse(env.step("book_aide", patient="A", start=1100, end=2000)["ok"])
        self.assertTrue(env.step("book_aide", patient="A", start=1100, end=1900)["ok"])
        self.assertEqual(env.evaluation_state()["spent"], 600)
        env.step("query_dme_vendors", patient="B")
        self.assertFalse(env.step("order_dme", patient="B", vendor="alt")["ok"])
        self.assertEqual(env.evaluation_state()["spent"], 600)

    def test_home_care_one_slot_and_consent_violation(self):
        env = Environment()
        self.assertTrue(env.step("book_home_care", patient="A")["ok"])
        self.assertFalse(env.step("book_home_care", patient="A")["ok"])
        self.assertEqual(len(env.evaluation_state()["services"]), 1)
        self.assertEqual(env.evaluation_state()["consent_violations"][0]["kind"], "home_care")

    def test_later_day_consent_is_specific_and_not_inferred_from_holding(self):
        env = Environment()
        env.step("notify", person="A", patient="A", decision="hold")
        self.assertEqual(env.evaluation_state()["consent_violations"], [])
        env.step("call", person="A", topic="consent_discharge_time", time=1950)
        self.assertTrue(env.step("schedule_discharge", patient="A", depart=1950, ride="transport")["ok"])
        self.assertEqual(env.evaluation_state()["consent_violations"], [])
        env.step("cancel_discharge", patient="A")
        self.assertTrue(env.step("schedule_discharge", patient="A", depart=1960, ride="transport")["ok"])
        self.assertEqual(env.evaluation_state()["consent_violations"][0]["kind"], "later_day")

    def test_earliest_departure_and_transport_lead(self):
        env = Environment()
        self.assertFalse(env.step("schedule_discharge", patient="A", depart=1004, ride="transport")["ok"])
        self.advance_to(env, 990)
        self.assertFalse(env.step("schedule_discharge", patient="A", depart=1007, ride="transport")["ok"])
        self.assertTrue(env.step("schedule_discharge", patient="A", depart=1011, ride="transport")["ok"])

    def test_cancel_reschedule_leaves_no_ghost_departure(self):
        env = Environment()
        env.step("schedule_discharge", patient="A", depart=1005, ride="transport")
        env.step("cancel_discharge", patient="A")
        env.step("schedule_discharge", patient="A", depart=1950, ride="transport")
        self.advance_to(env, 1080)
        self.assertNotIn("A", env.evaluation_state()["departures"])
        self.advance_to(env, 1950)
        self.assertEqual(env.evaluation_state()["departures"]["A"], 1950)

    def test_cancellation_must_finish_before_departure(self):
        env = Environment()
        env.step("schedule_discharge", patient="A", depart=1005, ride="transport")
        self.advance_to(env, 1002)
        self.assertFalse(env.step("cancel_discharge", patient="A")["ok"])
        self.assertEqual(env.evaluation_state()["departures"]["A"], 1005)

    def test_no_second_departure(self):
        env = Environment()
        env.step("schedule_discharge", patient="C", depart=990, ride="family")
        self.advance_to(env, 990)
        self.assertFalse(env.step("schedule_discharge", patient="C", depart=1100, ride="transport")["ok"])

    def test_full_requirement_window_must_fit_horizon(self):
        env = Environment()
        self.assertFalse(env.step("schedule_discharge", patient="A", depart=END - 1440, ride="transport")["ok"])
        self.assertTrue(env.step("schedule_discharge", patient="A", depart=END - 1440 - 45, ride="transport")["ok"])

    def test_capacity_request_submission_boundary(self):
        for request_time, expected in ((990, 1020), (991, 1140), (1200, 1205)):
            with self.subTest(request_time=request_time):
                env = Environment("impossible")
                self.advance_to(env, request_time)
                response = env.step("request_capacity_decision", reason_codes=["coverage_unresolved"])
                self.assertEqual(response["opens_at"], expected)
                scores = self.finish(env)
                self.assertEqual(scores["escalation"]["first_request_time"], request_time)
                self.assertEqual(scores["escalation"]["escalated_early"], request_time <= 990)

    def test_redundant_inquiries_and_interruption_minutes(self):
        env = Environment("allowed_twin")
        env.step("call", person="son", topic="availability", patient="A")
        env.step("send_portal_message", person="spouse", topic="pickup", patient="C")
        env.step("page_attending", patient="C", question="Requirements?")
        env.step("request_capacity_decision", reason_codes=["coverage_unresolved"])
        scores = self.finish(env)
        self.assertEqual(scores["inquiry_cost"], {"redundant_inquiries": 4, "agent_minutes": 31})
        self.assertEqual(scores["stakeholder_costs"]["interruptions"]["son"], {"count": 1, "minutes": 10})

    def test_invalid_wait_cannot_rewind_or_skip_beyond_end(self):
        env = Environment()
        for minutes in (-1, END, 1.5, True, "10"):
            self.assertFalse(env.step("wait", minutes=minutes)["ok"])
            self.assertEqual(env.evaluation_state()["now"], 900)

    def test_interval_union_is_exact(self):
        self.assertEqual(covered_minutes(10, 100, [(0, 20), (15, 30), (30, 80), (90, 120)]), 80)
        self.assertFalse(covers(10, 100, [(0, 80), (90, 120)]))
        self.assertTrue(covers(10, 100, [(0, 80), (80, 120)]))


if __name__ == "__main__":
    unittest.main()
