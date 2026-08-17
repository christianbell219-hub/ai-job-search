"""Contract checks for fork dashboard + thin command wrappers on synced upstream."""

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
        self.assertIn("deadline", text)
        self.assertIn("drafted", text)
        self.assertIn("tools/dashboard.py", text)


class RankUpskillContract(unittest.TestCase):
    def test_rank_persists_gaps(self) -> None:
        text = read(".claude/commands/rank.md")
        self.assertIn('"gaps"', text)
        self.assertIn("deadline", text)
        self.assertIn("language_gate", text)
        self.assertIn("work_mode", text)

    def test_upskill_reads_gaps(self) -> None:
        text = read(".claude/skills/upskill/SKILL.md")
        self.assertIn("gaps", text)
        self.assertIn("seen_jobs.json", text)


class HandoffContract(unittest.TestCase):
    def test_apply_records_drafted_with_deadline(self) -> None:
        text = read(".claude/commands/apply.md")
        self.assertIn("Step 6b", text)
        self.assertIn("job_posting.md", text)
        self.assertIn("`drafted`", text)
        self.assertIn("deadline", text)
        self.assertIn("job_search_tracker.csv", text)
        self.assertIn("contact.md", text)
        self.assertIn("hiring_contact", text)
        self.assertIn("Step 0b: Resolve hiring contact", text)

    def test_scrape_and_upskill_command_wrappers_exist(self) -> None:
        scrape = read(".claude/commands/scrape.md")
        upskill = read(".claude/commands/upskill.md")
        self.assertTrue(scrape.lstrip().startswith("# /scrape"))
        self.assertTrue(upskill.lstrip().startswith("# /upskill"))
        self.assertIn("Do not fork this spec", scrape)
        self.assertIn("Do not fork this spec", upskill)
        self.assertIn("gaps", upskill)
        self.assertIn("workplace mode", scrape)
        self.assertIn("ghost/expired", scrape)

    def test_portals_document_enabled_toggle(self) -> None:
        scraper = read(".claude/skills/job-scraper/SKILL.md")
        self.assertIn("enabled: false", scraper)
        sample = read(".agents/skills/jobindex-search/SKILL.md")
        self.assertIn("enabled:", sample)

    def test_canonical_tracker_status_underscores(self) -> None:
        outcome = read(".claude/commands/outcome.md")
        docs = read("documents/README.md")
        self.assertIn("underscores, never spaces", outcome)
        self.assertIn("`drafted`", outcome)
        self.assertIn("no_response", docs)
        self.assertIn("offer_declined", docs)
        self.assertIn("contact.md", docs)
        self.assertIn("/setup` ignores", docs)

    def test_scraper_honors_enabled_toggle(self) -> None:
        text = read(".claude/skills/job-scraper/SKILL.md")
        self.assertIn("enabled: false", text)
        self.assertIn("Honor the `enabled` toggle", text)
        self.assertIn("hiring_contact", text)
        self.assertIn("work_mode", text)


class DashboardPresenceContract(unittest.TestCase):
    def test_dashboard_entrypoints_exist(self) -> None:
        self.assertTrue((ROOT / "tools" / "dashboard.py").is_file())
        self.assertTrue((ROOT / "tools" / "job_pipeline.py").is_file())
        self.assertTrue((ROOT / "dashboard" / "index.html").is_file())
        self.assertTrue((ROOT / "dashboard" / "img" / "atmosphere.webp").is_file())


if __name__ == "__main__":
    unittest.main()
