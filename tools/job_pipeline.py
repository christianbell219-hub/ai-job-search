#!/usr/bin/env python3
"""Read/write the job-search files the dashboard and /status both use.

Stdlib only. Never invents tracker rows or job postings.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Any

TRACKER_HEADER = [
    "date",
    "company",
    "sector",
    "role",
    "role_type",
    "channel",
    "status",
    "contact_person",
    "fit_rating",
    "notes",
    "cv_file",
    "cover_letter_file",
    "source",
    "deadline",
]

# Tracker CSV vocabulary (mirrors /outcome). Archive outcome.md may still use
# interview_only / in_progress — those are not written to the tracker column.
CANONICAL_STATUSES = frozenset(
    {
        "drafted",
        "applied",
        "interview",
        "offer",
        "hired",
        "rejected",
        "no_response",
        "offer_declined",
        "withdrawn",
    }
)

STATUS_ALIASES = {
    "no response": "no_response",
    "offer declined": "offer_declined",
    "waiting": "applied",
}

FINAL_STATUSES = frozenset(
    {
        "hired",
        "rejected",
        "no_response",
        "offer_declined",
        "withdrawn",
    }
)

WRITABLE_STATUSES = frozenset(CANONICAL_STATUSES)

SILENT_DAYS = 14
ALLOWED_FILE_PREFIXES = ("cv/", "cover_letters/", "documents/applications/")

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---", re.S)
_ENABLED_LINE_RE = re.compile(r"^enabled:\s*(true|false)\s*$", re.I | re.M)
_NAME_LINE_RE = re.compile(r"^name:\s*(\S+)\s*$", re.M)
_CONTACT_FIELD_RE = re.compile(r"^\*\*([^*]+):\*\*\s*(.*)$", re.M)


def normalize_status(raw: str | None) -> str:
    value = (raw or "").strip().lower()
    if not value:
        return "applied"
    return STATUS_ALIASES.get(value, value)


def parse_iso_date(raw: str | None) -> date | None:
    text = (raw or "").strip()[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def archive_slug(company: str, role: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", f"{company}_{role}".lower()).strip("_")


def read_tracker(root: Path) -> list[dict[str, str]]:
    path = root / "job_search_tracker.csv"
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return []
    reader = csv.DictReader(StringIO(text))
    rows: list[dict[str, str]] = []
    for raw in reader:
        if not raw:
            continue
        row = {key: (raw.get(key) or "").strip() for key in TRACKER_HEADER}
        if not row["company"] and not row["role"]:
            continue
        rows.append(row)
    return rows


def write_tracker(root: Path, rows: list[dict[str, str]]) -> None:
    path = root / "job_search_tracker.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACKER_HEADER, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in TRACKER_HEADER})


def classify_row(row: dict[str, str], today: date, silent_days: int = SILENT_DAYS) -> str:
    status = normalize_status(row.get("status"))
    if status in FINAL_STATUSES:
        return "closed"
    if status == "offer":
        return "offer"
    if status == "interview":
        return "interview"
    # drafted: open but never sent — never "silent"
    applied = parse_iso_date(row.get("date"))
    if status == "applied" and applied is not None:
        if today - applied >= timedelta(days=silent_days):
            notes = (row.get("notes") or "").lower()
            if not re.search(r"\b(replied|reply|interview|offer|follow-?up sent|followed up)\b", notes):
                return "silent"
    return "waiting"


def read_seen_jobs(root: Path) -> dict[str, Any]:
    path = root / "job_scraper" / "seen_jobs.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    seen = data.get("seen") if isinstance(data, dict) else None
    return seen if isinstance(seen, dict) else {}


def tracker_keys(rows: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(r["company"].lower(), r["role"].lower()) for r in rows}


def scrape_backlog(seen: dict[str, Any], applied: set[tuple[str, str]]) -> dict[str, Any]:
    counts = {"new": 0, "ranked": 0, "expired": 0, "skipped": 0, "other": 0}
    ranked: list[dict[str, Any]] = []
    for key, entry in seen.items():
        if not isinstance(entry, dict):
            continue
        status = str(entry.get("status") or "new")
        company = str(entry.get("company") or "")
        title = str(entry.get("title") or "")
        tracked = (company.lower(), title.lower()) in applied
        if status == "expired":
            counts["expired"] += 1
        elif status == "ranked" and not tracked:
            counts["ranked"] += 1
            gaps = entry.get("gaps")
            if gaps is None:
                gaps = entry.get("rank_gaps") or []
            ranked.append(
                {
                    "key": key,
                    "title": title,
                    "company": company,
                    "url": entry.get("url") or "",
                    "rank_score": entry.get("rank_score"),
                    "rank_verdict": entry.get("rank_verdict") or "",
                    "gaps": gaps if isinstance(gaps, list) else [],
                    "deadline": entry.get("deadline") or "",
                    "work_mode": entry.get("work_mode") or "",
                }
            )
        elif status == "new":
            counts["new"] += 1
        elif status == "skipped":
            counts["skipped"] += 1
        else:
            counts["other"] += 1
    ranked.sort(key=lambda item: (-(item["rank_score"] or 0), item["company"]))
    return {"counts": counts, "ranked": ranked}


def _parse_contact(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    text = path.read_text(encoding="utf-8")
    fields = {match.group(1).strip().lower(): match.group(2).strip() for match in _CONTACT_FIELD_RE.finditer(text)}
    return {
        "name": fields.get("name", ""),
        "title": fields.get("title", ""),
        "confidence": fields.get("confidence", ""),
        "source": fields.get("source", ""),
        "salutation": fields.get("salutation used", ""),
    }


def _parse_outcome_status(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(r"\*\*Status:\*\*\s*(\S+)", path.read_text(encoding="utf-8"))
    return normalize_status(match.group(1)) if match else ""


def load_archives(root: Path) -> dict[str, dict[str, Any]]:
    base = root / "documents" / "applications"
    archives: dict[str, dict[str, Any]] = {}
    if not base.is_dir():
        return archives
    for folder in sorted(base.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        posting = folder / "job_posting.md"
        excerpt = ""
        if posting.is_file():
            excerpt = posting.read_text(encoding="utf-8").strip()[:400]
        pdfs = [str(p.relative_to(root)) for p in folder.glob("*.pdf")]
        archives[folder.name] = {
            "folder": str(folder.relative_to(root)),
            "has_posting": posting.is_file(),
            "has_cv": (folder / "cv_draft.tex").is_file(),
            "has_cover": (folder / "cover_letter.tex").is_file(),
            "has_outcome": (folder / "outcome.md").is_file(),
            "has_offer": (folder / "offer.md").is_file(),
            "outcome_status": _parse_outcome_status(folder / "outcome.md"),
            "contact": _parse_contact(folder / "contact.md"),
            "excerpt": excerpt,
            "pdfs": pdfs,
        }
    return archives


def _pdf_beside(root: Path, tex_path: str) -> str | None:
    if not tex_path:
        return None
    pdf = Path(tex_path).with_suffix(".pdf")
    if (root / pdf).is_file():
        return str(pdf).replace("\\", "/")
    return None


def list_portals(root: Path) -> list[dict[str, Any]]:
    skills = root / ".agents" / "skills"
    portals: list[dict[str, Any]] = []
    if not skills.is_dir():
        return portals
    for skill_md in sorted(skills.glob("*/SKILL.md")):
        if not (skill_md.parent / "cli" / "src" / "cli.ts").is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        name_match = _NAME_LINE_RE.search(text)
        name = name_match.group(1) if name_match else skill_md.parent.name
        enabled_match = _ENABLED_LINE_RE.search(text)
        enabled = True if enabled_match is None else enabled_match.group(1).lower() == "true"
        portals.append(
            {
                "name": name,
                "path": str(skill_md.relative_to(root)),
                "enabled": enabled,
            }
        )
    return portals


def set_portal_enabled(root: Path, name: str, enabled: bool) -> dict[str, Any]:
    for portal in list_portals(root):
        if portal["name"] != name:
            continue
        path = root / portal["path"]
        text = path.read_text(encoding="utf-8")
        line = f"enabled: {'true' if enabled else 'false'}"
        if _ENABLED_LINE_RE.search(text):
            text = _ENABLED_LINE_RE.sub(line, text, count=1)
        else:
            if re.search(r"^version:\s*.+$", text, re.M):
                text = re.sub(r"^(version:\s*.+)$", rf"\1\n{line}", text, count=1, flags=re.M)
            elif text.startswith("---\n"):
                text = "---\n" + line + "\n" + text[4:]
            else:
                raise ValueError(f"cannot insert enabled flag into {portal['path']}")
        path.write_text(text, encoding="utf-8")
        return {"name": name, "enabled": enabled, "path": portal["path"]}
    raise FileNotFoundError(f"unknown portal: {name}")


def update_tracker_status(
    root: Path,
    company: str,
    role: str,
    status: str,
    today: date | None = None,
) -> dict[str, str]:
    canonical = normalize_status(status)
    if canonical not in WRITABLE_STATUSES:
        raise ValueError(f"invalid status: {status}")
    rows = read_tracker(root)
    today = today or date.today()
    matched: dict[str, str] | None = None
    for row in rows:
        if row["company"].lower() == company.lower() and row["role"].lower() == role.lower():
            matched = row
            break
    if matched is None:
        raise FileNotFoundError(f"no tracker row for {company} / {role}")
    matched["status"] = canonical
    note = f"{today.isoformat()} dashboard: status → {canonical}"
    existing = matched.get("notes") or ""
    matched["notes"] = f"{existing}; {note}".strip("; ") if existing else note
    write_tracker(root, rows)
    return matched


def file_is_allowed(rel_path: str) -> bool:
    cleaned = rel_path.replace("\\", "/").lstrip("/")
    if ".." in Path(cleaned).parts or cleaned.startswith("/"):
        return False
    return any(cleaned.startswith(prefix) for prefix in ALLOWED_FILE_PREFIXES)


def resolve_allowed_file(root: Path, rel_path: str) -> Path:
    cleaned = rel_path.replace("\\", "/").lstrip("/")
    if not file_is_allowed(cleaned):
        raise PermissionError("path not allowed")
    target = (root / cleaned).resolve()
    root_resolved = root.resolve()
    if not str(target).startswith(str(root_resolved)):
        raise PermissionError("path not allowed")
    if not target.is_file():
        raise FileNotFoundError(cleaned)
    return target


def build_state(root: Path, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rows = read_tracker(root)
    archives = load_archives(root)
    applications = []
    buckets = {"waiting": 0, "silent": 0, "interview": 0, "offer": 0, "closed": 0}
    for row in rows:
        bucket = classify_row(row, today)
        buckets[bucket] += 1
        slug = archive_slug(row["company"], row["role"])
        archive = archives.get(slug, {})
        cv_pdf = _pdf_beside(root, row.get("cv_file") or "")
        cover_pdf = _pdf_beside(root, row.get("cover_letter_file") or "")
        applications.append(
            {
                **row,
                "status": normalize_status(row.get("status")),
                "bucket": bucket,
                "archive": archive,
                "cv_pdf": cv_pdf,
                "cover_pdf": cover_pdf,
                "commands": {
                    "apply": f"/apply {row['source']}".strip() if row.get("source") else "/apply",
                    "interview": f"/interview {row['company']}",
                    "followup": f"/outcome followup {row['company']}",
                    "outcome": f"/outcome {row['company']}",
                },
            }
        )
    seen = read_seen_jobs(root)
    backlog = scrape_backlog(seen, tracker_keys(rows))
    empty = not rows and not seen
    return {
        "today": today.isoformat(),
        "empty": empty,
        "buckets": buckets,
        "applications": applications,
        "backlog": backlog,
        "portals": list_portals(root),
    }
