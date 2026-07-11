#!/usr/bin/env python3
"""Revealed-preference engine for the AI Job Search feedback loop.

Reads the actions you have already taken - jobs scraped/ranked in
`job_scraper/seen_jobs.json` and applications logged in `job_search_tracker.csv`
- and distills a weighted "taste" model: which role terms, companies, and
sectors you gravitate toward (applied to, evaluated, ranked highly) versus the
ones you pass on (skipped, ranked low).

`/refine` consumes this model to propose sharper `/scrape` queries. The
arithmetic lives here so it is deterministic and unit-tested; the query
synthesis and the human approval stay in the command spec - the same split as
`salary_lookup.py` (tool) and `/apply` (command).

The signal is *revealed preference*: it grows and sharpens the more you use the
tool, and it works from your very first scrape - no resolved outcomes required.

Stdlib only. Run from anywhere: python3 tools/preference_model.py [--json]
"""

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEEN = ROOT / "job_scraper" / "seen_jobs.json"
DEFAULT_TRACKER = ROOT / "job_search_tracker.csv"

# Applications are logged with these columns (see /outcome, /upskill).
TRACKER_FINAL_STATUSES = {"hired", "rejected", "no response", "offer declined",
                          "withdrawn", "offer_declined", "no_response"}

# Weight each action contributes to the terms of the job it touched. Positive =
# drawn toward, negative = avoided. Applying is the strongest revealed signal;
# skipping is a clear negative; ranking is passive and weighted lightly.
W_APPLIED = 3.0
W_EVALUATED = 2.0
W_RANKED_STRONG = 2.0   # rank_score >= 75
W_RANKED_GOOD = 1.0     # 60 <= rank_score < 75
W_RANKED_WEAK = -1.0    # rank_score < 30
W_FIT_HIGH = 1.0
W_FIT_LOW = -1.0
W_PRACTICAL_CLEAR = 1.0  # practical_fit >= 70 (from the ranking layer)
W_SKIPPED = -1.5

# Minimal stopword list - drop true glue words, keep role/seniority/domain terms
# (those are exactly the signal we want to learn).
STOPWORDS = {
    "the", "of", "and", "for", "with", "to", "in", "a", "an", "at", "on",
    "or", "job", "role", "position", "vacancy", "opening", "m", "f", "d",
}

_TOKEN_RE = re.compile(r"[^a-z0-9+#]+")


def tokenize(text):
    """Lowercase and split a title/role string into meaningful terms."""
    if not text:
        return []
    tokens = _TOKEN_RE.split(text.lower())
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def load_seen(path=DEFAULT_SEEN):
    """Load seen_jobs.json. Missing or malformed file -> empty model."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"seen": {}}
    if not isinstance(data, dict) or not isinstance(data.get("seen"), dict):
        return {"seen": {}}
    return data


def load_tracker(path=DEFAULT_TRACKER):
    """Load applied jobs from the tracker CSV. Missing file -> []."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    rows = list(csv.DictReader(text.splitlines()))
    return [r for r in rows if (r.get("company") or "").strip()]


def entry_weight(entry):
    """Signed revealed-preference weight for one seen_jobs.json entry."""
    w = 0.0
    status = (entry.get("status") or "").lower()
    fit = (entry.get("fit") or "").lower()
    if status == "evaluated":
        w += W_EVALUATED
    elif status == "skipped":
        w += W_SKIPPED
    if fit == "high":
        w += W_FIT_HIGH
    elif fit == "low":
        w += W_FIT_LOW
    rank = entry.get("rank_score")
    if isinstance(rank, (int, float)) and not isinstance(rank, bool):
        if rank >= 75:
            w += W_RANKED_STRONG
        elif rank >= 60:
            w += W_RANKED_GOOD
        elif rank < 30:
            w += W_RANKED_WEAK
    pf = entry.get("practical_fit")
    if isinstance(pf, (int, float)) and not isinstance(pf, bool) and pf >= 70:
        w += W_PRACTICAL_CLEAR
    return w


def _signal_strength(counts):
    """Confidence in the model, driven by *deliberate* actions."""
    deliberate = counts["applied"] + counts["evaluated"] + counts["skipped"]
    if deliberate >= 10:
        return "high"
    if deliberate >= 3:
        return "medium"
    return "low"


def _top(mapping, positive=True, limit=10):
    items = [(term, round(w, 1)) for term, w in mapping.items()
             if (w > 0 if positive else w < 0)]
    items.sort(key=lambda kv: (kv[1], kv[0]), reverse=positive)
    if not positive:
        items.sort(key=lambda kv: (kv[1], kv[0]))
    return items[:limit]


def compute_preferences(seen, tracker_rows):
    """Aggregate revealed preferences from seen jobs + applications."""
    role_w = defaultdict(float)
    role_jobs = defaultdict(int)
    company_w = defaultdict(float)
    sector_w = defaultdict(float)
    counts = {"seen_total": 0, "ranked": 0, "evaluated": 0, "skipped": 0, "applied": 0}

    for entry in seen.get("seen", {}).values():
        counts["seen_total"] += 1
        status = (entry.get("status") or "").lower()
        if status in ("ranked", "evaluated", "skipped"):
            counts[status] += 1
        w = entry_weight(entry)
        if w == 0:
            continue
        seen_terms = set()
        for term in tokenize(entry.get("title", "")):
            role_w[term] += w
            if term not in seen_terms:
                role_jobs[term] += 1
                seen_terms.add(term)
        company = (entry.get("company") or "").strip().lower()
        if company:
            company_w[company] += w

    for row in tracker_rows:
        counts["applied"] += 1
        for field in ("role", "role_type"):
            for term in tokenize(row.get(field, "")):
                role_w[term] += W_APPLIED
                role_jobs[term] += 1
        company = (row.get("company") or "").strip().lower()
        if company:
            company_w[company] += W_APPLIED
        sector = (row.get("sector") or "").strip().lower()
        if sector:
            sector_w[sector] += W_APPLIED

    liked_roles = [{"term": t, "weight": w, "jobs": role_jobs[t]}
                   for t, w in _top(role_w, positive=True)]
    disliked_roles = [{"term": t, "weight": w, "jobs": role_jobs[t]}
                      for t, w in _top(role_w, positive=False)]

    return {
        "generated": date.today().isoformat(),
        "counts": counts,
        "signal_strength": _signal_strength(counts),
        "liked": {
            "roles": liked_roles,
            "companies": [{"term": t, "weight": w} for t, w in _top(company_w, positive=True)],
            "sectors": [{"term": t, "weight": w} for t, w in _top(sector_w, positive=True)],
        },
        "disliked": {
            "roles": disliked_roles,
        },
    }


def format_report(prefs):
    c = prefs["counts"]
    lines = [
        "## Revealed-preference model",
        f"Signal strength: {prefs['signal_strength'].upper()} "
        f"(applied {c['applied']}, evaluated {c['evaluated']}, skipped {c['skipped']}, "
        f"ranked {c['ranked']}, seen {c['seen_total']})",
        "",
    ]
    if prefs["signal_strength"] == "low":
        lines.append("Not enough deliberate actions yet - treat suggestions as directional, "
                     "not statistical. The model sharpens as you rank, evaluate, and apply.")
        lines.append("")

    def block(title, items, key="weight", extra=None):
        lines.append(f"### {title}")
        if not items:
            lines.append("(none yet)")
        for it in items:
            note = f" [{it['jobs']} jobs]" if "jobs" in it else ""
            lines.append(f"- {it['term']}  (weight {it[key]}){note}")
        lines.append("")

    block("Drawn toward — role terms", prefs["liked"]["roles"])
    block("Drawn toward — companies", prefs["liked"]["companies"])
    block("Drawn toward — sectors", prefs["liked"]["sectors"])
    if prefs["disliked"]["roles"]:
        block("Passing on — role terms", prefs["disliked"]["roles"])
    return "\n".join(lines).rstrip() + "\n"


def build_model(seen_path=DEFAULT_SEEN, tracker_path=DEFAULT_TRACKER):
    return compute_preferences(load_seen(seen_path), load_tracker(tracker_path))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Revealed-preference engine for /refine")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report")
    parser.add_argument("--seen", default=str(DEFAULT_SEEN), help="Path to seen_jobs.json")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="Path to job_search_tracker.csv")
    args = parser.parse_args(argv)

    prefs = build_model(args.seen, args.tracker)
    if args.json:
        print(json.dumps(prefs, indent=2))
    else:
        print(format_report(prefs), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
