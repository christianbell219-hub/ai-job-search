# /status - Pipeline view of the job search

You are presenting a read-only snapshot of the hunt: what has been drafted or applied to, what is waiting, what has gone silent, and what is still in the scrape backlog. The data already lives in the tracker, `seen_jobs.json`, and the application archives; this command is the view. It never applies, never ranks, and never edits profile files.

The same data is on the optional local board: `python3 tools/dashboard.py` → http://127.0.0.1:8765. Prefer `/status` in Claude when you want a narrative; use the board for status clicks and portal toggles.

Follow these steps **in order**.

---

## Step 0: Parse Input

`$ARGUMENTS` may contain:

- Nothing → full pipeline
- A company name → that application only (tracker row + archive)
- `--silent` → only rows that look stale (see Step 2)

---

## Step 1: Load State

Read, do not write:

1. `job_search_tracker.csv` — if missing, say so and continue with scrape/archive data only. Header (must match `/outcome` Step 1.1):
   ```
   date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source,deadline
   ```
2. `job_scraper/seen_jobs.json` — if missing, treat the scrape backlog as empty.
3. `documents/applications/*/outcome.md` (and `contact.md` if present) via Glob. Skip `in_progress` conclusions for calibration talk; still show them as open.

Today's date is the system date. Do not invent rows.

---

## Step 2: Classify tracker rows

Use the **Tracker status vocabulary** from `/outcome` (underscore spellings). When reading, accept legacy spaced aliases (`no response`, `offer declined`).

**Final** (closed): `hired`, `rejected`, `no_response`, `withdrawn`, `offer_declined`.

**Open** otherwise, including `drafted`, `applied`, `interview`, `offer`, and blanks.

**Silent:** open, status is `applied`, and the tracker `date` is **14 or more days** ago, and `notes` do not record a later contact (`followed up`, reply, interview, offer). **`drafted` is never silent** — nothing was sent. Do not auto-mark `no_response` — that is `/outcome`.

Bucket each open row as:

- `offer` — offer received, not accepted/declined
- `interview` — interview in progress or scheduled
- `silent` — applied and waiting too long
- `waiting` — drafted, recently applied, or another open status that is not silent/interview/offer

Show the `deadline` column when present. Mark a deadline within 7 days and one that has already passed the same way `/outcome` does.

---

## Step 3: Scrape backlog

From `seen_jobs.json` `seen` entries, count:

- `new` — not yet ranked
- `ranked` — ranked, not applied (exclude any company+role already in the tracker)
- `expired` — closed/ghost/deadline
- `skipped` / other

For ranked rows, prefer the stored `gaps` array (not a renamed field). Do not re-fetch postings. This is a count, not a re-rank.

---

## Step 4: Present

```
## Job search status — YYYY-MM-DD

| Bucket | Count |
|--------|-------|
| Waiting (drafted / applied <14 days) | N |
| Silent (applied, ≥14 days, no reply) | N |
| Interview | N |
| Offer | N |
| Closed (hired / rejected / no response / …) | N |
| Scrape: new / ranked / expired | A / B / C |

### Needs attention
- Silent: <Company> — <Role> (applied YYYY-MM-DD). `/outcome <company>` or `/outcome followup <company>`.
- Offer: <Company> — <Role>. `/outcome <company>` for the offer briefing.
- Deadline soon / passed on drafted: <Company> — <Role> (deadline YYYY-MM-DD).

### Tracker (open)
| Company | Role | Status | Date | Deadline | Fit |
| ... |

### Ranked backlog (not yet applied)
| Score | Company | Role | Top gaps |
| ... |
Copy `/apply <url>` for any you want to draft.
```

Keep the tables short. End with one line: drafting stays in Claude; the local dashboard only edits tracker status and portal `enabled` flags.

---

## Rules

1. **Read-only.** Never write the tracker, `seen_jobs.json`, archives, or profile files from `/status`.
2. **No invented jobs.** Empty files → say the pipeline is empty; suggest `/scrape` then `/rank`.
3. **Silence is a prompt, not a resolution.** Suggest `/outcome`; never set `no_response` from `/status`.
