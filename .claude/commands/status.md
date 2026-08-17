# /status - Pipeline view of the job search

You are presenting a read-only snapshot of the hunt: what has been applied to, what is waiting, what has gone silent, and what is still in the scrape backlog. The data already lives in the tracker, `seen_jobs.json`, and the application archives; this command is the view. It never applies, never ranks, and never edits profile files.

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

1. `job_search_tracker.csv` — if missing, say so and continue with scrape/archive data only. Header:
   ```
   date,company,sector,role,role_type,channel,status,contact_person,fit_rating,notes,cv_file,cover_letter_file,source
   ```
2. `job_scraper/seen_jobs.json` — if missing, treat the scrape backlog as empty.
3. `documents/applications/*/outcome.md` (and `contact.md` if present) via Glob. Skip `in_progress` conclusions for calibration talk; still show them as open.

Today's date is the system date. Do not invent rows.

---

## Step 2: Classify tracker rows

**Final** statuses (closed): `hired`, `rejected`, `no_response`, `withdrawn`, `offer_declined`, `interview_only`. When reading, treat spaced aliases (`no response`, `offer declined`) as the underscore form; `/outcome` and the dashboard write underscores only.

**Open** otherwise, including `applied`, `interview`, `offer`, `in_progress`, and blanks.

**Silent:** open, status is `applied` (or equivalent "waiting after apply"), and the tracker `date` is **14 or more days** ago, and `notes` do not record a later contact. 14 days matches the follow-up etiquette in `07-interview-prep.md`. Do not auto-mark `no_response` — that is `/outcome`.

Bucket each open row as:

- `offer` — offer received, not accepted/declined
- `interview` — interview in progress or scheduled
- `silent` — waiting too long
- `waiting` — applied recently, or another open status that is not silent/interview/offer

---

## Step 3: Scrape backlog

From `seen_jobs.json` `seen` entries, count:

- `new` — not yet ranked
- `ranked` — ranked, not applied (exclude any company+role already in the tracker)
- `expired` — closed/ghost/deadline
- `skipped` / other

Do not re-fetch postings. This is a count, not a re-rank.

---

## Step 4: Present

```
## Job search status — YYYY-MM-DD

| Bucket | Count |
|--------|-------|
| Waiting (applied, <14 days) | N |
| Silent (applied, ≥14 days, no reply) | N |
| Interview | N |
| Offer | N |
| Closed (hired / rejected / no response / …) | N |
| Scrape: new / ranked / expired | A / B / C |

### Needs attention
- Silent: <Company> — <Role> (applied YYYY-MM-DD). `/outcome <company>` to follow up or mark no_response.
- Offer: <Company> — <Role>. `/outcome <company>` for the offer briefing.
- Interview: <Company> — <Role>. `/interview <company>` if a round is coming up.
- Ranked backlog ≥8 and nothing new applied this week: suggest `/apply` on a shortlist number, or `/rank` if many are still `new`.

### Open applications
| Date | Company | Role | Status | Contact | Fit | Notes (trimmed) |
|------|---------|------|--------|---------|-----|-----------------|

### Scrape backlog
<N> new, <M> ranked (not in tracker), <E> expired. Dead postings stay expired; do not resurrect them.
```

Rules:

- If the tracker is empty and seen_jobs is empty, tell the user to run `/setup` (if profile placeholders remain) then `/scrape`. Do not fake a pipeline.
- Every company/role traces to a file you read.
- **Needs attention** lists only real silent/offer/interview rows, not hypotheticals.
- Then offer handoffs: `/outcome` for silent or offer, `/interview` for a scheduled round, `/rank` if `new` count is high, `/upskill` if ranked gaps have piled up.

---

## Important Rules

1. **Read-only.** Do not edit the tracker, `seen_jobs.json`, archives, or profile files. `/outcome` and the local dashboard own status writes; this command only presents.
2. **Do not invent applications.** Empty files mean an empty table.
3. **Silence is a prompt, not a resolution.** Suggest `/outcome`; never set `no_response` from `/status`.
4. **14-day silent window** is the default; if the user asks for a different cutoff, use it for this run only.
