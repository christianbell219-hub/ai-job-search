"""Contract checks for remote-search and hiring-contact wiring.

These are markdown/instruction contracts: /scrape, /rank, and /apply are
prompt specs, not Python. The tests lock the phrases those specs must keep
so a later edit cannot silently drop remote flags or invent hiring managers.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class RemoteSearchContract(unittest.TestCase):
    def test_search_queries_has_workplace_filter_placeholders(self) -> None:
        text = read(".claude/skills/job-scraper/search-queries.md")
        self.assertIn("## Workplace filter", text)
        self.assertIn("[YOUR_WORKPLACE_MODE]", text)
        self.assertIn("remote-only", text)
        self.assertIn("remote-ok", text)
        self.assertIn("[YOUR_REMOTE_REGIONS]", text)
        self.assertIn("[YOUR_EMPLOYER_COUNTRY_CONSTRAINT]", text)
        self.assertIn("Portal remote flags", text)
        self.assertIn('-l "Remote" --remote remote', text)
        self.assertIn("--region [YOUR_FREEHIRE_REGIONS],none", text)
        self.assertIn("--remote helt", text)
        self.assertIn("do **not** append city", text)

    def test_scrape_skill_passes_remote_flags_and_keeps_true_remote(self) -> None:
        text = read(".claude/skills/job-scraper/SKILL.md")
        self.assertIn("Workplace filter", text)
        self.assertIn("--remote remote", text)
        self.assertIn("work_mode", text)
        self.assertIn("Workplace-aware geography", text)
        self.assertNotIn(
            "Skip jobs that require relocation or are clearly outside commute range.",
            text,
        )
        self.assertIn("fake remote", text)

    def test_eval_and_rank_pass_true_remote_with_overseas_hq(self) -> None:
        eval_text = read(
            ".claude/skills/job-application-assistant/04-job-evaluation.md"
        )
        rank_text = read(".claude/commands/rank.md")
        self.assertIn("San Francisco, CA", eval_text)
        self.assertIn("EU timezone", eval_text)
        self.assertIn("PASS even if the posting's city string is another country", eval_text)
        self.assertIn("fake remote", rank_text)
        self.assertIn("Do **not** veto true remote", rank_text)

    def test_add_portal_documents_remote_or_post_filter(self) -> None:
        text = read(".claude/commands/add-portal.md")
        self.assertIn("unsupported — post-filter from detail", text)
        self.assertIn("--remote", text)


class HiringContactContract(unittest.TestCase):
    def test_apply_has_confidence_ladder_and_no_invented_names(self) -> None:
        text = read(".claude/commands/apply.md")
        self.assertIn("Step 0b: Resolve hiring contact", text)
        self.assertIn("**High — named in the posting", text)
        self.assertIn("**Medium — portal hiring-team field.**", text)
        self.assertIn("**Low — inferred from public pages.**", text)
        self.assertIn("Never invent a person", text)
        self.assertIn("Do not** scrape LinkedIn people search", text)
        self.assertIn("contact.md", text)

    def test_cover_letter_salutation_requires_confidence(self) -> None:
        text = read(
            ".claude/skills/job-application-assistant/06-cover-letter-templates.md"
        )
        self.assertIn("Never print an inferred name", text)
        self.assertIn("user confirmed", text)

    def test_setup_asks_workplace_mode(self) -> None:
        text = read(".claude/commands/setup.md")
        self.assertIn("Workplace mode", text)
        self.assertIn("remote-ok", text)
        self.assertIn("[YOUR_WORKPLACE_MODE]", text)


if __name__ == "__main__":
    unittest.main()
