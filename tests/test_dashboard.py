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

    def test_refuses_non_localhost_host(self) -> None:
        self.assertEqual(dashboard_mod.main(["--host", "0.0.0.0"]), 2)


if __name__ == "__main__":
    unittest.main()
