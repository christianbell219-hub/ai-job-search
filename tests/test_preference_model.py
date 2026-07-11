"""Tests for tools/preference_model.py — the revealed-preference engine."""

import unittest

from tools.preference_model import (
    tokenize,
    entry_weight,
    load_seen,
    load_tracker,
    compute_preferences,
    W_APPLIED,
    W_EVALUATED,
    W_SKIPPED,
    W_RANKED_STRONG,
)


def seen(*entries):
    return {"seen": {str(i): e for i, e in enumerate(entries)}}


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


class EntryWeightTests(unittest.TestCase):
    def test_evaluated_is_positive(self):
        self.assertEqual(entry_weight({"status": "evaluated"}), W_EVALUATED)

    def test_skipped_is_negative(self):
        self.assertEqual(entry_weight({"status": "skipped"}), W_SKIPPED)

    def test_strong_rank_and_high_fit_stack(self):
        w = entry_weight({"status": "ranked", "fit": "high", "rank_score": 82})
        self.assertEqual(w, W_RANKED_STRONG + 1.0)  # fit_high = 1.0

    def test_practical_clear_bonus(self):
        w = entry_weight({"rank_score": 90, "practical_fit": 75})
        self.assertEqual(w, W_RANKED_STRONG + 1.0)  # strong rank + practical bonus

    def test_weak_rank_is_negative(self):
        self.assertEqual(entry_weight({"rank_score": 12}), -1.0)

    def test_bool_is_not_treated_as_score(self):
        # True is an int subclass; must not be read as rank_score 1
        self.assertEqual(entry_weight({"rank_score": True}), 0.0)

    def test_neutral_entry_is_zero(self):
        self.assertEqual(entry_weight({"status": "new"}), 0.0)


class LoadGracefulTests(unittest.TestCase):
    def test_missing_seen_returns_empty(self):
        self.assertEqual(load_seen("/nonexistent/seen.json"), {"seen": {}})

    def test_missing_tracker_returns_empty(self):
        self.assertEqual(load_tracker("/nonexistent/tracker.csv"), [])


class ComputePreferencesTests(unittest.TestCase):
    def test_applied_role_terms_outrank_skipped(self):
        tracker = [{"company": "Novo", "sector": "pharma", "role": "Data Scientist",
                    "role_type": "data science"}]
        model = compute_preferences(
            seen({"title": "Sales Manager", "status": "skipped", "fit": "low"}),
            tracker,
        )
        liked = [r["term"] for r in model["liked"]["roles"]]
        disliked = [r["term"] for r in model["disliked"]["roles"]]
        self.assertIn("scientist", liked)
        self.assertIn("data", liked)
        self.assertIn("sales", disliked)
        self.assertNotIn("scientist", disliked)

    def test_company_and_sector_signal_from_application(self):
        model = compute_preferences(
            seen(),
            [{"company": "Novo Nordisk", "sector": "Pharma", "role": "ML Engineer",
              "role_type": ""}],
        )
        self.assertEqual(model["liked"]["companies"][0]["term"], "novo nordisk")
        self.assertEqual(model["liked"]["sectors"][0]["term"], "pharma")

    def test_counts_and_signal_strength(self):
        model = compute_preferences(
            seen(
                {"title": "A Engineer", "status": "evaluated"},
                {"title": "B Engineer", "status": "skipped", "fit": "low"},
                {"title": "C Engineer", "status": "ranked", "rank_score": 80},
            ),
            [{"company": "X", "role": "Engineer", "sector": "tech"}],
        )
        self.assertEqual(model["counts"]["applied"], 1)
        self.assertEqual(model["counts"]["evaluated"], 1)
        self.assertEqual(model["counts"]["skipped"], 1)
        self.assertEqual(model["counts"]["ranked"], 1)
        self.assertEqual(model["counts"]["seen_total"], 3)
        # deliberate = applied(1)+evaluated(1)+skipped(1) = 3 -> medium
        self.assertEqual(model["signal_strength"], "medium")

    def test_low_signal_when_only_passive_ranking(self):
        model = compute_preferences(
            seen({"title": "Data Scientist", "status": "ranked", "rank_score": 70}),
            [],
        )
        self.assertEqual(model["signal_strength"], "low")

    def test_empty_inputs_do_not_crash(self):
        model = compute_preferences({"seen": {}}, [])
        self.assertEqual(model["signal_strength"], "low")
        self.assertEqual(model["liked"]["roles"], [])
        self.assertEqual(model["disliked"]["roles"], [])

    def test_repeated_applications_accumulate_weight(self):
        rows = [{"company": "A", "role": "Data Scientist", "sector": "s"},
                {"company": "B", "role": "Data Scientist", "sector": "s"}]
        model = compute_preferences(seen(), rows)
        scientist = next(r for r in model["liked"]["roles"] if r["term"] == "scientist")
        self.assertEqual(scientist["weight"], round(2 * W_APPLIED, 1))
        self.assertEqual(scientist["jobs"], 2)


if __name__ == "__main__":
    unittest.main()
