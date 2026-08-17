---
name: scrape
description: >
  Finds new job postings matching your profile via installed portal-search CLIs
  (LinkedIn, local job boards, and any skills added with /add-portal). Deduplicates
  across runs. Triggers on: job scrape, find jobs, search jobs, new jobs, job search,
  scrape jobs, /scrape
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(bun --version), Bash(bun run .agents/skills/*/cli/src/cli.ts *), WebFetch, WebSearch, Agent, AskUserQuestion
---

# Job Scraper

---

## How It Works

This skill searches job portals using the **installed portal-search CLIs** in
`.agents/skills/` (plus WebSearch as a fallback), using queries from your profile.
It deduplicates against previously seen jobs and the application tracker, and
presents new matches with a quick fit assessment.

## Invocation

The user triggers this skill by saying things like:
- "Find new jobs"
- "Scrape for jobs"
- "Any new positions?"
- "/scrape"

Optional arguments:
- A focus area, e.g. "/scrape data science" or "/scrape geophysics"
- "broad" to run all search categories, e.g. "/scrape broad"

---

## Execution Steps

### Step 0: Load State

1. Read `job_scraper/seen_jobs.json` (create if missing - start with `{"seen": {}}`)
2. Read `job_search_tracker.csv` to extract already-applied companies+roles
3. Read `search-queries.md` (this directory) for the search strategy, including the **Workplace filter** (`Mode`, remote regions/timezones, employer-country constraint, portal remote flags)

### Step 1: Search

Read `search-queries.md` (this directory) for the search strategy. By default, run the top 3 priority query categories. If the user said "broad", run all categories. If the user specified a focus area (e.g. "data science"), prioritize queries from that category. If they said "remote", run the remote pass only.

Read **Workplace filter → Mode** before constructing any CLI call:

- `onsite` — local/commute queries only; do not pass remote flags
- `hybrid` — local queries; pass a portal's partial-remote flag only if the SKILL.md documents one (e.g. Jobbank `--remote delvist`)
- `remote-ok` — run **both** a local commute pass and a remote pass
- `remote-only` — remote pass only; do not append city to keyword queries
- Missing or still `[YOUR_WORKPLACE_MODE]` — treat as `remote-ok` if the profile/deal-breakers mention remote work, otherwise `onsite`

**Use the installed CLI tools as the primary search mechanism.** Fall back to `WebSearch` only for portals that do not have a CLI skill, or if `bun` is unavailable on the system.

#### 1a. Check bun availability

```bash
bun --version
```

If this fails (bun not installed), skip to **1c (WebSearch fallback)** for all portals and note the fallback in the Step 5 output.

#### 1b. Run CLI tools (primary — run these in parallel where possible)

Discover installed **portal CLI** skills: every `.agents/skills/*/SKILL.md` whose directory also contains `cli/src/cli.ts`. Skip other skills in that tree (taste/design skills live under `.claude/skills/` and are not job boards). Each portal SKILL.md documents that portal's exact CLI flags. **Use each portal's own documented interface — do not guess flags.** `/add-portal` skills are picked up automatically when they include the CLI.

**Portal on/off:** if a skill's YAML frontmatter has `enabled: false`, skip it entirely and list it as `skipped (disabled)` in the Step 5 summary. Missing `enabled` means **on** (same as `enabled: true`). Do not delete the skill directory to silence a board.

For each **enabled** portal skill:

1. Read its `SKILL.md` to find the correct `bun run …` invocation and supported flags.
2. Translate the query terms from `search-queries.md` into that portal's flag format (e.g. `--key`, `--search-string`, `--query`, filter codes — whatever the portal's SKILL.md specifies).
3. **Workplace flags:** when Mode is `remote-only` or `remote-ok`, pass that portal's **documented** remote flag from `search-queries.md` → Portal remote flags (and the portal's own SKILL.md). Do not guess a city keyword as a substitute except where the SKILL.md says the portal has no remote parameter (Jobindex keyword pass without city; Jobnet/Jobdanmark post-filter after `detail`). Shipped mapping:
   - **linkedin-search:** global remote pass `-l "Remote" --remote remote`; optional second pass `-l "<city from search-queries>" --remote remote` for remote-in-this-market. Never pass a city as `-l` without `--remote` on a remote pass.
   - **freehire-search:** `--remote remote` and `--region <codes>,none` so unresolved-geo remotes are not dropped.
   - **jobbank-search:** `--remote helt` (or `delvist` when Mode is `hybrid`).
   - **jobindex-search:** no API remote filter — on a remote pass do **not** append city to `--query`; add a keyword pass with `remote` / `hjemmearbejde` and classify `work_mode` from `detail` text.
   - **jobnet-search / jobdanmark-search:** no search-time remote flag — do not restrict `--region`/`--municipality` on a remote-only pass; classify from location/description after `detail`.
4. Scope to the last 14 days using the portal's supported recency flag (`--jobage`, `--since <YYYY-MM-DD>`, `--order PublicationDate`, etc. — as documented per portal).
5. Cap results to ~20 per call using the portal's limit flag.
6. Use `--format json` for machine-readable output.

Run all portal CLI calls in parallel where possible using the Agent tool. Collect all `results` arrays into a single pool for Step 2, keeping each result tagged with its source portal skill (for Step 2 `detail` lookups).

If a CLI tool exits with a non-zero code, log the error message and continue — do not abort the whole search.

#### 1c. WebSearch fallback

Use `WebSearch` for:
- Portals listed in `search-queries.md` that do **not** have a corresponding directory under `.agents/skills/`
- Any portal whose CLI fails at runtime
- When bun is unavailable (Step 1a failed)

Use the site-specific query strings from `search-queries.md` directly as WebSearch queries for these portals.

### Step 2: Fetch & Parse

For each promising result from Step 1:

**From CLI results:** Search output already includes title, company, location, date,
and URL. For jobs worth a deeper look, fetch full detail with that portal's `detail`
command (see its SKILL.md — do not guess flags) to extract **key requirements**,
**application deadline**, a brief description snippet, **work_mode**, and any **named
contact** already in the posting or detail payload (Jobnet `contactPersons`, LinkedIn
`hiringTeam`, a "contact:" line). Do not web-search for a hiring manager during scrape.
If LinkedIn `detail` returns `"closed": true` or exits `NOT_FOUND`, set that job's
`status` to `expired` and do not present it. Same for other portals whose `detail` or
fetched page says the listing is closed or the deadline has passed.

**From WebSearch results:** Use `WebFetch` on the posting URL and extract the same
fields manually.

Classify `work_mode` as `remote` | `hybrid` | `onsite` | `unknown` from, in order:
the portal's workplace field if present, location text (`Remote`, `Fjernarbejde`,
`Hjemmearbejde`, `Hybrid`, `On-site`), then description. An HQ city in another
country does **not** make the job `onsite` when the posting is fully remote.

For every candidate:
- Skip if the URL or company+title combo already exists in `seen_jobs.json`
- Skip if the company+role already appears in `job_search_tracker.csv`
- Apply **Rule 3** (workplace + commute) before presenting

### Step 3: Quick Fit Assessment

For each new job, do a rapid fit check (NOT the full evaluation from `04-job-evaluation.md` - just a quick signal):

- **High match**: Role directly involves your core skills
- **Medium match**: Role is adjacent to your experience
- **Low match**: Role requires significant skills you lack

### Step 4: Deduplicate & Store

1. Add ALL fetched jobs (new and skipped) to `seen_jobs.json` with structure:
```json
{
  "seen": {
    "<url_or_company_title_key>": {
      "title": "...",
      "company": "...",
      "url": "...",
      "first_seen": "YYYY-MM-DD",
      "fit": "high/medium/low",
      "status": "new/skipped/evaluated/ranked/expired",
      "work_mode": "remote/hybrid/onsite/unknown",
      "hiring_contact": null
    }
  }
}
```

`/rank` extends this schema additively: ranked entries also carry `rank_score` (0–100 overall score), `rank_verdict` (fit band, e.g. "strong fit"), `rank_date` (ISO date of ranking), `rank_gaps` (array of honest gap strings), and `rank_strengths`. The `status` field is set to `"ranked"`. Do not drop these fields when re-writing entries.

2. Only present jobs NOT already in the seen list or tracker.

### Step 5: Present Results

Present new jobs in a table sorted by fit (high first):

```
## New Job Matches - YYYY-MM-DD

Found X new positions (Y high, Z medium, W low match).

| # | Fit | Title | Company | Location | Deadline | URL |
|---|-----|-------|---------|----------|----------|-----|
| 1 | High | ... | ... | Remote (EU) | ... | [Link](...) |

Location must reflect `work_mode`: `Remote ([region])`, `Hybrid, [city]`, or the
office city — not an overseas HQ city for a fully remote role.

### High-Match Highlights
For each high-match job, add 2-3 bullet points:
- Why it matches your profile
- Key requirements to check
- Any red flags
```

After presenting, ask:
> "Want to apply to any of these? Give me the number(s) and I'll start the full `/apply` workflow."

If the user picks a number, run the **`/apply` command workflow** on that job's URL (`.claude/commands/apply.md`) — ghost check, hiring-contact ladder, drafter-reviewer, PDF/ATS verification. Do **not** invoke the job-application-assistant skill as a shortcut; that path skips those steps. Do **not** write `job_search_tracker.csv` from scrape — `/apply` (record-as-applied) and `/outcome` own tracker rows.

If any `new` jobs remain after this run, also suggest `/rank` so they are scored against the fit framework. Emphasize `/rank` when there are roughly 8 or more. (`/rank` sets the `ranked` and `expired` status values in `seen_jobs.json`; treat both as already-seen for dedup purposes.)

---

## Important Rules

1. **Never fabricate job postings.** Only present jobs from actual CLI search/detail output or WebSearch/WebFetch results.
2. **Respect deduplication.** Always check seen_jobs.json AND job_search_tracker.csv before presenting.
3. **Workplace-aware geography.** Read Mode from `search-queries.md`. Skip **onsite** (and hybrid-with-required-office-days) jobs that are outside the commute tiers. Do **not** skip jobs classified `remote` that match Remote regions/timezones and Employer country constraint — an HQ city overseas is not relocation. Skip **fake remote**: title or location says remote but the posting requires relocation or a specific office 5 days a week. For `onsite` mode, skip true-remote jobs. For `remote-only` mode, skip onsite jobs outside any stated exception.
4. **Only open positions.** Skip postings with expired deadlines or those marked as closed.
5. **Be efficient with detail fetches.** Don't run `detail` or WebFetch on every search hit — pre-filter by title/snippet, then fetch only promising matches.
6. **Parallel searches.** Run portal CLI searches in parallel; use WebSearch only for gaps the CLIs don't cover.
