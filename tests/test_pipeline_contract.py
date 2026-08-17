"""Contract checks for pipeline commands: ghost postings, /status, rank→upskill, follow-up."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class GhostPostingContract(unittest.TestCase):
    def test_apply_stops_on_closed_listing(self) -> None:
        text = read(".claude/commands/apply.md")
        self.assertIn("Ghost / closed check", text)
        self.assertIn("no longer accepting applications", text)
        self.assertIn('"closed": true', text)
        self.assertIn('"status": "expired"', text)

    def test_rank_uses_linkedin_detail_closed(self) -> None:
        text = read(".claude/commands/rank.md")
        self.assertIn("Ghost check", text)
        self.assertIn('"closed": true', text)


class StatusCommandContract(unittest.TestCase):
    def test_status_command_exists_and_is_readonly(self) -> None:
        text = read(".claude/commands/status.md")
        self.assertTrue(text.lstrip().startswith("# /status"))
        self.assertIn("Read-only", text)
        self.assertIn("Silent", text)
        self.assertIn("14", text)
        self.assertIn("job_search_tracker.csv", text)
        self.assertIn("seen_jobs.json", text)


class RankUpskillContract(unittest.TestCase):
    def test_rank_persists_gaps(self) -> None:
        text = read(".claude/commands/rank.md")
        self.assertIn("rank_gaps", text)

    def test_upskill_reads_rank_gaps(self) -> None:
        text = read(".claude/skills/upskill/SKILL.md")
        self.assertIn("rank_gaps", text)
        self.assertIn("seen_jobs.json", text)


class InterviewFollowupContract(unittest.TestCase):
    def test_interview_has_followup_pack(self) -> None:
        text = read(".claude/commands/interview.md")
        self.assertIn("--followup", text)
        self.assertIn("Thank-you note", text)
        self.assertIn("interview_followup_", text)
        self.assertIn("never invent a name", text)


class HandoffContract(unittest.TestCase):
    def test_apply_archives_and_can_record_tracker(self) -> None:
        text = read(".claude/commands/apply.md")
        self.assertIn("Draft archive (always)", text)
        self.assertIn("job_posting.md", text)
        self.assertIn("cv_draft.tex", text)
        self.assertIn("Record as applied", text)
        self.assertIn("fit_rating", text)
        self.assertIn("job_search_tracker.csv", text)
        self.assertIn("hiring_contact", text)

    def test_scrape_hands_off_to_apply_not_skill_shortcut(self) -> None:
        text = read(".claude/skills/job-scraper/SKILL.md")
        self.assertIn("full `/apply` workflow", text)
        self.assertIn(".claude/commands/apply.md", text)
        self.assertNotIn("invoke the **job-application-assistant** skill workflow", text)
        self.assertNotIn("### Step 6: Update Tracker (Optional)", text)
        self.assertIn("enabled: false", text)
        self.assertIn("skipped (disabled)", text)
        self.assertIn("cli/src/cli.ts", text)

    def test_scrape_and_upskill_command_wrappers_exist(self) -> None:
        scrape = read(".claude/commands/scrape.md")
        upskill = read(".claude/commands/upskill.md")
        self.assertTrue(scrape.lstrip().startswith("# /scrape"))
        self.assertTrue(upskill.lstrip().startswith("# /upskill"))
        self.assertIn("Do not fork this spec", scrape)
        self.assertIn("Do not fork this spec", upskill)

    def test_add_portal_documents_enabled_flag(self) -> None:
        text = read(".claude/commands/add-portal.md")
        self.assertIn("enabled: true", text)
        self.assertIn("enabled: false", text)

    def test_canonical_tracker_status_underscores(self) -> None:
        outcome = read(".claude/commands/outcome.md")
        docs = read("documents/README.md")
        self.assertIn("underscore values only", outcome)
        self.assertIn("`no_response`", docs)
        self.assertIn("`offer_declined`", docs)
        self.assertNotIn("no response` / `offer declined", outcome)


if __name__ == "__main__":
    unittest.main()
