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


if __name__ == "__main__":
    unittest.main()
