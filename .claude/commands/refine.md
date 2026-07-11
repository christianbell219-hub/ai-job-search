# /refine - Learn From What You Apply To and Sharpen the Search

You are running the feedback loop that makes the search smarter the more the user uses it. Every scrape, rank, evaluation, and application is a **revealed preference** - a signal about the roles, companies, and sectors the user is actually drawn to (or passes on). `/refine` distills those signals into an accumulating taste model and proposes sharper `/scrape` queries so the next batch surfaces more of what fits.

It works from the very first scrape - it does **not** need resolved outcomes (that is `/calibrate`'s job, later). Signal starts weak and sharpens with use.

**Discipline (mirrors `/outcome` → `/setup`):** this command *accumulates the model* and *proposes* query changes, but only rewrites `search-queries.md` with the user's explicit approval. It never fabricates preferences and never edits the profile skill files silently.

Follow these steps **in order**.

---

## Step 0: Parse Input

`$ARGUMENTS` may contain:

- Nothing → build the model, persist it, and propose query changes for approval.
- `--show` → build and print the model only; propose nothing and write nothing.
- `--focus <area>` → bias the proposed queries toward a direction the user names (still grounded in the model).

---

## Step 1: Build the Revealed-Preference Model

Run the deterministic engine (local, read-only, stdlib):

```bash
python3 tools/preference_model.py --json
```

It reads `job_scraper/seen_jobs.json` (scraped/ranked/evaluated/skipped jobs, including `rank_score` and `practical_fit` from the ranking layer) and `job_search_tracker.csv` (applications), and returns:

- `counts` and `signal_strength` (`low` / `medium` / `high`, driven by *deliberate* actions - applied, evaluated, skipped)
- `liked.roles` / `liked.companies` / `liked.sectors` - weighted terms the user is drawn toward
- `disliked.roles` - weighted terms the user passes on

If `signal_strength` is `low`, say so plainly and treat everything below as **directional, not statistical**. Do not overhaul the search on thin data. If both state files are empty, tell the user to run `/scrape` (and rank/apply to a few roles) first, then stop.

Do not recompute these weights yourself - the tool is the source of truth for the arithmetic. Your job is interpretation.

---

## Step 2: Persist the Model

Write the model to `job_scraper/preferences.json` (personal data - already gitignored). This file is **additive and historical**: keep a short `history` array so the user can see how their taste has shifted over time.

```json
{
  "updated": "YYYY-MM-DD",
  "signal_strength": "low | medium | high",
  "counts": { "applied": N, "evaluated": N, "skipped": N, "ranked": N, "seen_total": N },
  "liked": { "roles": [...], "companies": [...], "sectors": [...] },
  "disliked": { "roles": [...] },
  "history": [
    { "date": "YYYY-MM-DD", "signal_strength": "...", "top_roles": ["...", "..."], "note": "what shifted since last run" }
  ]
}
```

On re-run, append a new `history` entry (never rewrite past ones) and refresh the top-level fields from the current model. Re-running is idempotent within a day: if an entry for today exists, update it rather than duplicating.

---

## Step 3: Propose Sharper Queries (approval required)

Read `.claude/skills/job-scraper/search-queries.md` and `.claude/skills/job-application-assistant/01-candidate-profile.md` (for the current target roles and location terms). Then propose **additive** changes, grounded strictly in the model:

1. **Amplify** - for the strongest `liked.roles`/`sectors`/`companies` not already well covered, propose new query lines in the matching priority block (reuse the file's existing site/flag format - do not invent portal syntax).
2. **Reprioritize** - if a `liked` direction consistently outweighs a current Priority 1 that the user rarely engages with, suggest swapping their priority order.
3. **De-emphasize** - for strong `disliked.roles`, suggest dropping or narrowing queries that mostly return those (e.g. add a negative term), but only when the signal is clear (multiple skips, not one).
4. **Adjacency (the "find more like this" step)** - propose 1-3 *new* role directions adjacent to what the user is drawn to but not yet in their queries (e.g. consistent "data scientist" + "nlp" engagement → suggest "applied scientist", "ML research engineer"). Label these clearly as suggestions to explore, with the reasoning from the model.

Present the proposal as a diff-style list grouped by priority block, then ask:

> **Apply these query changes?** Reply **yes** to apply all, or list the numbers to skip. These only add/adjust search queries - your profile and past history are untouched.

Wait for the response. Apply only confirmed items to `search-queries.md` with the Edit tool. If the user ran `--show`, skip this step entirely.

---

## Step 4: Confirm and Hand Off

Summarize:

> **Search refined from <N> tracked actions (signal: <strength>).**
> - Model saved to `job_scraper/preferences.json`
> - Applied: <query changes, or "none - directional only">
> - Drawn toward: <top 3 role terms>; passing on: <top disliked, if any>
>
> Run `/scrape` to pull a fresh batch against the sharpened queries. The more you rank and apply, the sharper this gets.

If `signal_strength` was `low`, add: "Come back to `/refine` after you've ranked and applied to a few more roles - the model needs a handful of deliberate actions before its suggestions are worth acting on."

---

## Important Rules

1. **Revealed preference, not outcomes.** `/refine` learns from what the user *does* (applies to, evaluates, skips, ranks). Outcome-based calibration (did it get interviews?) is `/calibrate`'s job.
2. **Propose, don't impose.** Query changes to `search-queries.md` always require explicit approval. The model file accumulates automatically; the search strategy does not change silently.
3. **Honor the signal floor.** On `low` signal, suggestions are directional only - never overhaul the search on a few data points.
4. **Additive and honest.** Never fabricate a preference the model does not show. `preferences.json` history is append-only. `search-queries.md` edits reuse its existing format and never touch profile files.
5. **The tool owns the math.** Weights and rankings come from `tools/preference_model.py`; this command interprets and synthesizes, it does not re-derive scores.
