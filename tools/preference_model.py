#!/usr/bin/env python3
"""Outcome-driven preference engine for the AI Job Search feedback loop.

This learns from what actually *converted*, not from what you merely applied to.
It reads your resolved applications from `job_search_tracker.csv` (the `status`
column `/outcome` maintains) and weights each role term, company, and sector by
how far the application got: interviews and offers are strong positive signal,
rejections and silence are negative. `/refine` then proposes sharper `/scrape`
queries pointed at what works.

Because it waits for outcomes, it stays quiet until you have recorded a handful
of resolved applications (`--min-outcomes`, default 3). Applications still
`applied`/`in_progress` are counted as *pending* and contribute no preference
signal - that is the "wait for outcomes" behavior by design.

The arithmetic lives here so it is deterministic and unit-tested; the query
synthesis and the human approval stay in the `/refine` command spec - the same
split as `salary_lookup.py` (tool) and `/apply` (command).

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
DEFAULT_TRACKER = ROOT / "job_search_tracker.csv"
DEFAULT_MIN_OUTCOMES = 3

# How far an application got, weighted for "find more like what converts".
# Reaching interviews is traction; an offer (even one you declined) is the
# strongest signal the role type fits you; rejection is a clear negative;
# silence is a weak negative (often volume/luck, not fit).
W_HIRED = 4.0
W_OFFER = 4.0
W_OFFER_DECLINED = 3.0
W_INTERVIEW = 2.5
W_REJECTED = -1.5
W_NO_RESPONSE = -0.5
W_WITHDRAWN = 0.0  # you pulled out - ambiguous, no fit signal

OUTCOME_WEIGHTS = {
    "hired": W_HIRED,
    "offer": W_OFFER,
    "offer declined": W_OFFER_DECLINED,
    "interview": W_INTERVIEW,
    "rejected": W_REJECTED,
    "no response": W_NO_RESPONSE,
    "withdrawn": W_WITHDRAWN,
}
# Positive-traction statuses (used for the "got interviews" count).
TRACTION = {"hired", "offer", "offer declined", "interview"}

STOPWORDS = {
    "the", "of", "and", "for", "with", "to", "in", "a", "an", "at", "on",
    "or", "job", "role", "position", "vacancy", "opening", "m", "f", "d",
}

_TOKEN_RE = re.compile(r"[^a-z0-9+#]+")


def tokenize(text):
    """Lowercase and split a role string into meaningful terms."""
    if not text:
        return []
    tokens = _TOKEN_RE.split(text.lower())
    return [t for t in tokens if len(t) >= 2 and t not in STOPWORDS]


def classify_status(raw):
    """Map a free-text tracker status to a canonical outcome key.

    Returns a key in OUTCOME_WEIGHTS for a resolved outcome, or None for a
    still-pending application (applied / in_progress / unknown) - which
    contributes no preference signal.
    """
    s = (raw or "").strip().lower()
    if not s:
        return None
    if "hire" in s:
        return "hired"
    if "offer" in s and "declin" in s:
        return "offer declined"
    if "offer" in s:
        return "offer"
    if "interview" in s:
        return "interview"
    if "reject" in s:
        return "rejected"
    if "withdraw" in s:
        return "withdrawn"
    if "no response" in s or "no_response" in s or "ghost" in s or "silence" in s:
        return "no response"
    return None  # applied / in_progress / anything unrecognised = pending


def load_tracker(path=DEFAULT_TRACKER):
    """Load application rows from the tracker CSV. Missing file -> []."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    rows = list(csv.DictReader(text.splitlines()))
    return [r for r in rows if (r.get("company") or "").strip()]


def _signal_strength(resolved):
    if resolved >= 7:
        return "high"
    if resolved >= 3:
        return "medium"
    return "low"


def _top(mapping, positive=True, limit=10):
    items = [(term, round(w, 1)) for term, w in mapping.items()
             if (w > 0 if positive else w < 0)]
    items.sort(key=lambda kv: (kv[1], kv[0]), reverse=positive)
    if not positive:
        items.sort(key=lambda kv: (kv[1], kv[0]))
    return items[:limit]


def compute_preferences(tracker_rows, min_outcomes=DEFAULT_MIN_OUTCOMES):
    """Aggregate outcome-driven preferences from resolved applications."""
    role_w = defaultdict(float)
    role_jobs = defaultdict(int)
    company_w = defaultdict(float)
    sector_w = defaultdict(float)
    counts = {"applications": 0, "resolved": 0, "pending": 0,
              "interviews_plus": 0, "rejected": 0, "no_response": 0}

    for row in tracker_rows:
        counts["applications"] += 1
        key = classify_status(row.get("status", ""))
        if key is None:
            counts["pending"] += 1
            continue
        counts["resolved"] += 1
        if key in TRACTION:
            counts["interviews_plus"] += 1
        elif key == "rejected":
            counts["rejected"] += 1
        elif key == "no response":
            counts["no_response"] += 1

        w = OUTCOME_WEIGHTS[key]
        if w == 0:
            continue
        seen_terms = set()
        for field in ("role", "role_type"):
            for term in tokenize(row.get(field, "")):
                role_w[term] += w
                if term not in seen_terms:
                    role_jobs[term] += 1
                    seen_terms.add(term)
        company = (row.get("company") or "").strip().lower()
        if company:
            company_w[company] += w
        sector = (row.get("sector") or "").strip().lower()
        if sector:
            sector_w[sector] += w

    resolved = counts["resolved"]
    liked_roles = [{"term": t, "weight": w, "jobs": role_jobs[t]}
                   for t, w in _top(role_w, positive=True)]
    disliked_roles = [{"term": t, "weight": w, "jobs": role_jobs[t]}
                      for t, w in _top(role_w, positive=False)]

    return {
        "generated": date.today().isoformat(),
        "min_outcomes": min_outcomes,
        "ready": resolved >= min_outcomes,
        "signal_strength": _signal_strength(resolved),
        "counts": counts,
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
        "## Outcome-driven preference model",
        f"Applications: {c['applications']}  |  resolved: {c['resolved']}  "
        f"(interviews+: {c['interviews_plus']}, rejected: {c['rejected']}, "
        f"no-response: {c['no_response']})  |  pending: {c['pending']}",
        f"Signal strength: {prefs['signal_strength'].upper()}",
        "",
    ]
    if not prefs["ready"]:
        need = prefs["min_outcomes"]
        lines.append(
            f"Waiting for outcomes: {c['resolved']} resolved of {need} needed before "
            f"refining. Record what happens to your applications with `/outcome` "
            f"(interviews, offers, rejections). Until then there is nothing to learn from."
        )
        return "\n".join(lines).rstrip() + "\n"

    def block(title, items):
        lines.append(f"### {title}")
        if not items:
            lines.append("(none yet)")
        for it in items:
            note = f" [{it['jobs']} apps]" if "jobs" in it else ""
            lines.append(f"- {it['term']}  (weight {it['weight']}){note}")
        lines.append("")

    block("What converts — role terms", prefs["liked"]["roles"])
    block("What converts — companies", prefs["liked"]["companies"])
    block("What converts — sectors", prefs["liked"]["sectors"])
    if prefs["disliked"]["roles"]:
        block("What stalls — role terms", prefs["disliked"]["roles"])
    return "\n".join(lines).rstrip() + "\n"


def build_model(tracker_path=DEFAULT_TRACKER, min_outcomes=DEFAULT_MIN_OUTCOMES):
    return compute_preferences(load_tracker(tracker_path), min_outcomes)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Outcome-driven preference engine for /refine")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a report")
    parser.add_argument("--tracker", default=str(DEFAULT_TRACKER), help="Path to job_search_tracker.csv")
    parser.add_argument("--min-outcomes", type=int, default=DEFAULT_MIN_OUTCOMES,
                        help="Resolved outcomes required before refining (default 3)")
    args = parser.parse_args(argv)

    prefs = build_model(args.tracker, args.min_outcomes)
    if args.json:
        print(json.dumps(prefs, indent=2))
    else:
        print(format_report(prefs), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
