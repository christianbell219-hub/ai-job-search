"""Tests for tools/preference_model.py — the outcome-driven preference engine."""

import unittest

from tools.preference_model import (
    tokenize,
    classify_status,
    load_tracker,
    compute_preferences,
    W_INTERVIEW,
    W_OFFER,
    W_REJECTED,
)


def rows(*specs):
    """Build tracker rows from (company, role, sector, status) tuples."""
    out = []
    for company, role, sector, status in specs:
        out.append({"company": company, "role": role, "role_type": "",
                    "sector": sector, "status": status})
    return out


class TokenizeTests(unittest.TestCase):
    def test_lowercases_and_splits(self):
        self.assertEqual(tokenize("Senior Data Scientist"), ["senior", "data", "scientist"])

    def test_drops_stopwords_and_short_tokens(self):
        self.assertEqual(tokenize("Head of ML"), ["head", "ml"])

    def test_keeps_plus_and_hash(self):
        self.assertIn("c++", tokenize("C++ Developer"))

    def test_empty_and_none(self):
        self.assertEqual(tokenize(""), [])
        self.assertEqual(tokenize(None), [])


class ClassifyStatusTests(unittest.TestCase):
    def test_pending_states_return_none(self):
        for s in ("applied", "in_progress", "in progress", "", "new", None):
            self.assertIsNone(classify_status(s))

    def test_resolved_outcomes(self):
        self.assertEqual(classify_status("Interview scheduled"), "interview")
        self.assertEqual(classify_status("1st interview done"), "interview")
        self.assertEqual(classify_status("hired!"), "hired")
        self.assertEqual(classify_status("offer received"), "offer")
        self.assertEqual(classify_status("offer declined"), "offer declined")
        self.assertEqual(classify_status("Rejected"), "rejected")
        self.assertEqual(classify_status("no response"), "no response")
        self.assertEqual(classify_status("withdrawn"), "withdrawn")

    def test_offer_declined_precedence_over_offer(self):
        self.assertEqual(classify_status("offer declined by me"), "offer declined")


class LoadGracefulTests(unittest.TestCase):
    def test_missing_tracker_returns_empty(self):
        self.assertEqual(load_tracker("/nonexistent/tracker.csv"), [])


class WaitForOutcomesTests(unittest.TestCase):
    def test_no_applications_is_not_ready(self):
        model = compute_preferences([])
        self.assertFalse(model["ready"])
        self.assertEqual(model["signal_strength"], "low")

    def test_only_pending_applications_wait(self):
        model = compute_preferences(rows(
            ("A", "Data Scientist", "tech", "applied"),
            ("B", "ML Engineer", "tech", "in_progress"),
        ))
        self.assertFalse(model["ready"])
        self.assertEqual(model["counts"]["pending"], 2)
        self.assertEqual(model["counts"]["resolved"], 0)
        # No preference signal is produced while waiting.
        self.assertEqual(model["liked"]["roles"], [])

    def test_ready_once_min_outcomes_resolved(self):
        model = compute_preferences(rows(
            ("A", "Data Scientist", "tech", "interview"),
            ("B", "Data Analyst", "tech", "rejected"),
            ("C", "ML Engineer", "tech", "offer"),
        ), min_outcomes=3)
        self.assertTrue(model["ready"])
        self.assertEqual(model["counts"]["resolved"], 3)
        self.assertEqual(model["signal_strength"], "medium")

    def test_min_outcomes_threshold_is_configurable(self):
        r = rows(("A", "DS", "t", "interview"), ("B", "DS", "t", "rejected"))
        self.assertFalse(compute_preferences(r, min_outcomes=3)["ready"])
        self.assertTrue(compute_preferences(r, min_outcomes=2)["ready"])


class OutcomeSignalTests(unittest.TestCase):
    def test_converting_roles_are_liked_stalling_roles_disliked(self):
        model = compute_preferences(rows(
            ("A", "Data Scientist", "pharma", "offer"),
            ("B", "Data Scientist", "pharma", "interview"),
            ("C", "Sales Manager", "retail", "rejected"),
        ))
        liked = [r["term"] for r in model["liked"]["roles"]]
        disliked = [r["term"] for r in model["disliked"]["roles"]]
        self.assertIn("scientist", liked)
        self.assertIn("sales", disliked)
        self.assertNotIn("scientist", disliked)

    def test_pending_application_contributes_no_signal(self):
        model = compute_preferences(rows(
            ("A", "Data Scientist", "pharma", "offer"),
            ("B", "Data Scientist", "pharma", "interview"),
            ("C", "Astronaut", "space", "applied"),  # pending -> ignored
        ))
        liked = [r["term"] for r in model["liked"]["roles"]]
        self.assertNotIn("astronaut", liked)

    def test_offer_outweighs_single_rejection_for_same_role(self):
        model = compute_preferences(rows(
            ("A", "Data Scientist", "t", "offer"),
            ("B", "Data Scientist", "t", "rejected"),
            ("C", "Data Scientist", "t", "interview"),
        ))
        scientist = next(r for r in model["liked"]["roles"] if r["term"] == "scientist")
        self.assertEqual(scientist["weight"], round(W_OFFER + W_REJECTED + W_INTERVIEW, 1))
        self.assertEqual(scientist["jobs"], 3)

    def test_company_and_sector_signal_from_conversions(self):
        model = compute_preferences(rows(
            ("Novo Nordisk", "Data Scientist", "Pharma", "interview"),
        ), min_outcomes=1)
        self.assertEqual(model["liked"]["companies"][0]["term"], "novo nordisk")
        self.assertEqual(model["liked"]["sectors"][0]["term"], "pharma")

    def test_counts_breakdown(self):
        model = compute_preferences(rows(
            ("A", "DS", "t", "interview"),
            ("B", "DS", "t", "offer"),
            ("C", "DS", "t", "rejected"),
            ("D", "DS", "t", "no response"),
            ("E", "DS", "t", "applied"),
        ))
        c = model["counts"]
        self.assertEqual(c["applications"], 5)
        self.assertEqual(c["resolved"], 4)
        self.assertEqual(c["pending"], 1)
        self.assertEqual(c["interviews_plus"], 2)
        self.assertEqual(c["rejected"], 1)
        self.assertEqual(c["no_response"], 1)


if __name__ == "__main__":
    unittest.main()
