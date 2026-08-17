"""Dashboard pipeline helpers: buckets, CSV writes, portal flags, localhost HTTP."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import threading
import unittest
from datetime import date, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import dashboard as dashboard_mod  # noqa: E402
import job_pipeline as jp  # noqa: E402


def _write_tracker(root: Path, rows: list[dict[str, str]]) -> None:
    path = root / "job_search_tracker.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=jp.TRACKER_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in jp.TRACKER_HEADER})


class ClassifyTests(unittest.TestCase):
    def test_empty_state_invents_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = jp.build_state(root, today=date(2026, 8, 17))
            self.assertTrue(state["empty"])
            self.assertEqual(state["applications"], [])
            self.assertEqual(state["buckets"]["waiting"], 0)
            self.assertEqual(state["backlog"]["counts"]["new"], 0)
            self.assertEqual(state["paste_inbox"], [])
            self.assertIsNone(state["gmail"]["last_sync"])
            self.assertEqual(state["rail"][0]["command"], "/scrape")

    def test_silent_is_applied_14_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tracker(
                root,
                [
                    {"date": "2026-08-01", "company": "Acme", "role": "Engineer", "status": "applied"},
                    {"date": "2026-08-16", "company": "Beta", "role": "Analyst", "status": "applied"},
                    {"date": "2026-07-01", "company": "OldCo", "role": "Lead", "status": "interview"},
                    {"date": "2026-07-01", "company": "Gone", "role": "Intern", "status": "rejected"},
                ],
            )
            state = jp.build_state(root, today=date(2026, 8, 17))
            buckets = {app["company"]: app["bucket"] for app in state["applications"]}
            self.assertEqual(buckets["Acme"], "silent")
            self.assertEqual(buckets["Beta"], "waiting")
            self.assertEqual(buckets["OldCo"], "interview")
            self.assertEqual(buckets["Gone"], "closed")
            self.assertFalse(state["empty"])

    def test_status_write_is_csv_edit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tracker(
                root,
                [{"date": "2026-08-01", "company": "Acme", "role": "Engineer", "status": "applied"}],
            )
            jp.update_tracker_status(root, "Acme", "Engineer", "no_response", today=date(2026, 8, 17))
            rows = jp.read_tracker(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "no_response")
            self.assertIn("no_response", rows[0]["notes"])
            with self.assertRaises(ValueError):
                jp.update_tracker_status(root, "Acme", "Engineer", "totally_new")

    def test_alias_reads_as_underscore(self) -> None:
        self.assertEqual(jp.normalize_status("no response"), "no_response")
        self.assertEqual(jp.normalize_status("offer declined"), "offer_declined")

    def test_ranked_backlog_excludes_tracker_company_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "job_scraper").mkdir()
            (root / "job_scraper" / "seen_jobs.json").write_text(
                json.dumps(
                    {
                        "seen": {
                            "u1": {
                                "title": "Engineer",
                                "company": "Acme",
                                "url": "https://example.com/1",
                                "status": "ranked",
                                "rank_score": 80,
                                "rank_gaps": ["No k8s"],
                            },
                            "u2": {
                                "title": "Scientist",
                                "company": "Other",
                                "url": "https://example.com/2",
                                "status": "ranked",
                                "rank_score": 70,
                                "rank_gaps": [],
                            },
                            "u3": {"title": "X", "company": "Y", "status": "expired"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            _write_tracker(
                root,
                [{"date": "2026-08-01", "company": "Acme", "role": "Engineer", "status": "applied"}],
            )
            state = jp.build_state(root, today=date(2026, 8, 17))
            self.assertEqual(state["backlog"]["counts"]["ranked"], 1)
            self.assertEqual(state["backlog"]["counts"]["expired"], 1)
            self.assertEqual(state["backlog"]["ranked"][0]["company"], "Other")

    def test_drafted_is_never_silent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tracker(
                root,
                [{"date": "2026-07-01", "company": "Acme", "role": "Engineer", "status": "drafted"}],
            )
            state = jp.build_state(root, today=date(2026, 8, 17))
            self.assertEqual(state["buckets"]["waiting"], 1)
            self.assertEqual(state["buckets"]["silent"], 0)
            self.assertEqual(state["applications"][0]["bucket"], "waiting")

    def test_ranked_gaps_field_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "job_scraper").mkdir()
            (root / "job_scraper" / "seen_jobs.json").write_text(
                json.dumps(
                    {
                        "seen": {
                            "u1": {
                                "title": "Scientist",
                                "company": "Other",
                                "status": "ranked",
                                "rank_score": 70,
                                "gaps": ["Limited Spark"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            state = jp.build_state(root, today=date(2026, 8, 17))
            self.assertEqual(state["backlog"]["ranked"][0]["gaps"], ["Limited Spark"])

    def test_needs_action_silent_deadline_and_ranked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "job_scraper").mkdir()
            (root / "job_scraper" / "seen_jobs.json").write_text(
                json.dumps(
                    {
                        "seen": {
                            "u1": {
                                "title": "Scientist",
                                "company": "Other",
                                "url": "https://example.com/job",
                                "status": "ranked",
                                "rank_score": 84,
                                "gaps": ["Spark"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            _write_tracker(
                root,
                [
                    {
                        "date": "2026-08-01",
                        "company": "Acme",
                        "role": "Engineer",
                        "status": "applied",
                    },
                    {
                        "date": "2026-08-10",
                        "company": "Beta",
                        "role": "Analyst",
                        "status": "drafted",
                        "deadline": "2026-08-18",
                    },
                    {
                        "date": "2026-08-16",
                        "company": "Gamma",
                        "role": "Lead",
                        "status": "offer",
                    },
                ],
            )
            state = jp.build_state(root, today=date(2026, 8, 17))
            kinds = {item["kind"] for item in state["needs_action"]}
            self.assertIn("silent", kinds)
            self.assertIn("drafted_deadline", kinds)
            self.assertIn("offer", kinds)
            self.assertIn("ranked", kinds)
            silent = next(a for a in state["needs_action"] if a["kind"] == "silent")
            self.assertEqual(silent["company"], "Acme")
            self.assertIn("/outcome followup Acme", silent["command"])
            drafted = next(a for a in state["needs_action"] if a["kind"] == "drafted_deadline")
            self.assertEqual(drafted["company"], "Beta")
            ranked = next(a for a in state["needs_action"] if a["kind"] == "ranked")
            self.assertEqual(ranked["command"], "/apply https://example.com/job")
            beta = next(a for a in state["applications"] if a["company"] == "Beta")
            self.assertEqual(beta["deadline_urgency"], "soon")

    def test_mark_submitted_is_drafted_to_applied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_tracker(
                root,
                [
                    {
                        "date": "2026-08-10",
                        "company": "Acme",
                        "role": "Engineer",
                        "status": "drafted",
                        "deadline": "2026-08-20",
                    }
                ],
            )
            updated = jp.update_tracker_status(
                root, "Acme", "Engineer", "applied", today=date(2026, 8, 17)
            )
            self.assertEqual(updated["status"], "applied")
            rows = jp.read_tracker(root)
            self.assertEqual(rows[0]["status"], "applied")
            self.assertIn("applied", rows[0]["notes"])
            self.assertEqual(rows[0]["deadline"], "2026-08-20")

    def test_paste_inbox_gmail_rail_and_unranked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            postings = root / "documents" / "postings"
            postings.mkdir(parents=True)
            (postings / "skip").mkdir()
            (postings / "notes.bin").write_bytes(b"nope")
            (postings / "blocked.txt").write_text("pasted JD", encoding="utf-8")
            (root / "gmail_sync").mkdir()
            (root / "gmail_sync" / "state.json").write_text(
                json.dumps(
                    {
                        "last_sync": "2026-08-16",
                        "processed_message_ids": ["m1", "m2"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "job_scraper").mkdir()
            (root / "job_scraper" / "seen_jobs.json").write_text(
                json.dumps({"seen": {"u1": {"title": "X", "company": "Y", "status": "new"}}}),
                encoding="utf-8",
            )
            state = jp.build_state(root, today=date(2026, 8, 17))
            self.assertFalse(state["empty"])
            self.assertEqual([item["name"] for item in state["paste_inbox"]], ["blocked.txt"])
            self.assertEqual(
                state["paste_inbox"][0]["command"],
                "/apply the posting in documents/postings/blocked.txt",
            )
            self.assertEqual(state["gmail"]["last_sync"], "2026-08-16")
            self.assertEqual(state["gmail"]["processed"], 2)
            self.assertEqual([item["command"] for item in state["rail"][:3]], ["/scrape", "/rank", "/status"])
            kinds = {item["kind"] for item in state["needs_action"]}
            self.assertIn("paste", kinds)
            self.assertIn("unranked", kinds)


class PortalAndPathTests(unittest.TestCase):
    def test_portal_enabled_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / ".agents" / "skills" / "demo-search" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            (skill.parent / "cli" / "src").mkdir(parents=True)
            (skill.parent / "cli" / "src" / "cli.ts").write_text("export {}\n", encoding="utf-8")
            skill.write_text(
                "---\nname: demo-search\nversion: 1.0.0\nenabled: true\ndescription: demo\n---\n# Demo\n",
                encoding="utf-8",
            )
            portals = jp.list_portals(root)
            self.assertEqual(portals[0]["enabled"], True)
            jp.set_portal_enabled(root, "demo-search", False)
            self.assertIn("enabled: false", skill.read_text(encoding="utf-8"))
            self.assertFalse(jp.list_portals(root)[0]["enabled"])

    def test_file_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "secret.txt").write_text("nope", encoding="utf-8")
            with self.assertRaises(PermissionError):
                jp.resolve_allowed_file(root, "../secret.txt")
            with self.assertRaises(PermissionError):
                jp.resolve_allowed_file(root, "CLAUDE.md")
            cv = root / "cv"
            cv.mkdir()
            pdf = cv / "main_acme.pdf"
            pdf.write_bytes(b"%PDF")
            self.assertEqual(jp.resolve_allowed_file(root, "cv/main_acme.pdf"), pdf.resolve())
            postings = root / "documents" / "postings"
            postings.mkdir(parents=True)
            paste = postings / "blocked.txt"
            paste.write_text("pasted posting", encoding="utf-8")
            self.assertEqual(
                jp.resolve_allowed_file(root, "documents/postings/blocked.txt"),
                paste.resolve(),
            )


class HttpTests(unittest.TestCase):
    def test_state_and_status_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = (date.today() - timedelta(days=20)).isoformat()
            _write_tracker(
                root,
                [{"date": old, "company": "Acme", "role": "Engineer", "status": "applied"}],
            )
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_mod.make_handler(root))
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            port = httpd.server_address[1]
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/state", timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["buckets"]["silent"], 1)
                req = Request(
                    f"http://127.0.0.1:{port}/api/status",
                    data=json.dumps(
                        {"company": "Acme", "role": "Engineer", "status": "interview"}
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urlopen(req, timeout=5) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertEqual(jp.read_tracker(root)[0]["status"], "interview")
                bad = Request(
                    f"http://127.0.0.1:{port}/file?path=../secret",
                    method="GET",
                )
                with self.assertRaises(HTTPError) as ctx:
                    urlopen(bad, timeout=5)
                self.assertEqual(ctx.exception.code, 403)
            finally:
                httpd.shutdown()
                httpd.server_close()

    def test_serves_dashboard_visuals(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), dashboard_mod.make_handler(ROOT))
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        try:
            for name in ("atmosphere.webp", "empty.webp", "backlog.webp", "rail.webp", "inbox.webp"):
                with urlopen(f"http://127.0.0.1:{port}/static/img/{name}", timeout=5) as resp:
                    body = resp.read()
                    self.assertEqual(resp.headers.get("Content-Type"), "image/webp")
                    self.assertGreater(len(body), 1000)
                    self.assertTrue(body.startswith(b"RIFF"))
            with urlopen(f"http://127.0.0.1:{port}/static/motion.js", timeout=5) as resp:
                self.assertIn("IntersectionObserver", resp.read().decode("utf-8"))
            with urlopen(f"http://127.0.0.1:{port}/", timeout=5) as resp:
                html = resp.read().decode("utf-8")
            self.assertIn('class="atmosphere"', html)
            self.assertIn("/static/img/empty.webp", html)
            self.assertIn("/static/img/rail.webp", html)
            self.assertIn("panel-strip", html)
            self.assertIn('id="needs"', html)
            self.assertIn('class="bento"', html)
            self.assertIn('id="rail"', html)
            self.assertIn('id="inbox"', html)
            self.assertIn("Paste inbox", html)
            self.assertIn("Mark submitted", (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8"))
            self.assertIn("needs_action", (ROOT / "tools" / "job_pipeline.py").read_text(encoding="utf-8"))
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_refuses_non_localhost_host(self) -> None:
        self.assertEqual(dashboard_mod.main(["--host", "0.0.0.0"]), 2)


if __name__ == "__main__":
    unittest.main()
