# /rank - Triage Scraped Jobs into a Ranked Shortlist

You are batch-scoring the jobs that `/scrape` has collected, so the user can decide where to spend `/apply` effort. `/scrape` finds and dedupes postings; `/apply` evaluates one at a time in depth. `/rank` is the bridge: it scores every new posting against the fit framework and returns a ranked shortlist.

`/rank` produces **triage scores**, not final evaluations. It scores from the posting text and the candidate profile only - no company research, no reviewer agent. `/apply`'s Step 1 evaluation (which adds company research) remains authoritative and always re-runs when the user applies.

Follow these steps **in order**.

---

## Step 0: Parse Input

`$ARGUMENTS` may contain:

- Nothing → rank all jobs with status `new` in `job_scraper/seen_jobs.json`
- A focus area (e.g. `/rank data science`) → rank only jobs whose title or stored fit-notes match the focus
- `--all` → re-rank every job that has not been applied to, including previously ranked ones (useful after the profile changes)
- `--top <N>` → shortlist size (default 5)
- `--by <quality|practical>` → primary sort key (default `quality`). `quality` sorts by the weighted fit score; `practical` sorts by the Practical Fit Ranking Layer score (salary / remote / visa / skill match). The other score is always shown as a column and used as the tiebreaker.

---

## Step 1: Load State

1. Read `job_scraper/seen_jobs.json`. If the file is missing or has no entries, tell the user to run `/scrape` first and stop.
2. Read `job_search_tracker.csv`. Build the exclusion set: any company+role already in the tracker is out of scope regardless of flags - it has been applied to or consciously tracked.
3. Select candidates: entries with status `new` (or all non-applied entries with `--all`), minus the exclusion set, filtered by the focus area if one was given.
4. If no candidates remain, say so ("Nothing new to rank - run /scrape to find fresh postings") and stop.
5. Read the scoring framework and profile **once**:
   - `.claude/skills/job-application-assistant/04-job-evaluation.md`
   - `.claude/skills/job-application-assistant/01-candidate-profile.md`

   From these, extract the **Practical Fit Ranking Layer** rubric and the candidate's reference values (salary expectation, remote preference + max commute, work authorization — see the "Work Preferences" section of the profile). Any reference value still holding a placeholder token means that sub-score is `N/A` for this run; note which ones so the layer degrades honestly instead of inventing constraints.

State how many jobs will be ranked before proceeding.

---

## Step 2: Batch-Fetch and Score

Dispatch parallel `general-purpose` agents via the **Agent tool**, ~5 jobs per agent (a single agent is fine for ≤5 jobs). Token-efficiency rules, consistent with `/apply`:

- Pass each agent everything it needs **inline in the prompt** - the job list (title, company, URL) and a compact scoring rubric extracted from the files you read in Step 1: the strong/moderate/weak skill match areas, direct/adjacent experience domains, behavioral thrive/drain factors, career goals, deal-breakers, the location constraints, and the **Practical Fit Ranking Layer** reference values (remote preference + max commute, work authorization). Do **not** make agents re-read the profile files.
- Agents fetch each posting URL with WebFetch and score **only from actually fetched content**. If a URL is dead, redirects to a listing page, or the posting has expired, the agent marks that job `expired` - it never scores from the title alone and never fabricates posting content.
- Agents also score the ranking layer from the posting text: **Remote Fit** (posting work model vs. the candidate's remote preference/commute) and **Visa Fit** (per L4 — authorized / sponsorship-offered / silent / explicitly-excluded), and extract any **stated salary range** verbatim plus the **work model** and **job country/city**. `Skill Match` reuses the `technical` score (do not compute a second number). The agent does **not** run the salary tool — the main context computes Salary Fit in Step 3, since `salary_lookup.py` is local.
- Scope is triage: posting text vs. rubric, plus the one **local** `salary_lookup.py` call in Step 3. **No company research, no web searches** - that depth belongs to `/apply`.

Each agent returns a JSON array, one object per job:

```json
{
  "key": "<the job's key in seen_jobs.json>",
  "status": "scored" | "expired",
  "scores": { "technical": 0-100, "experience": 0-100, "behavioral": 0-100, "career": 0-100 },
  "location": "PASS" | "FAIL" | "FLAG",
  "practical": {
    "remote_fit": 0-100,
    "visa_fit": 0-100,
    "visa_veto": true | false,
    "salary_range": "<verbatim from posting, or null>",
    "work_model": "remote" | "hybrid" | "onsite" | "unstated",
    "country": "<job country/city, or null>"
  },
  "deadline": "YYYY-MM-DD" | null,
  "strengths": ["1-3 bullets, grounded in the posting text"],
  "gaps": ["1-3 bullets, honest"],
  "language": "<posting language>"
}
```

Scoring uses the dimension definitions from `04-job-evaluation.md` verbatim, including the Practical Fit Ranking Layer (L1-L4). The honesty rule applies to triage too: gaps are stated, never smoothed over, and a posting that is a poor fit gets a low score even if it looks prestigious. Set `visa_veto: true` only when the posting **explicitly** rules out sponsorship the candidate needs.

---

## Step 3: Aggregate and Rank

Back in the main context, for each scored job:

1. Compute the overall **quality score** with the weighting from `04-job-evaluation.md` (Technical 30%, Experience 25%, Behavioral 15%, Career Alignment 30%; location is unweighted).
2. Map to the framework's verdict bands (Strong Fit 75+, Good Fit 60-74, Moderate Fit 45-59, Weak Fit 30-44, Poor Fit <30).
3. **Compute the Practical Fit Ranking Layer** (`04-job-evaluation.md` → "Practical Fit Ranking Layer"):
   - **Skill Match** = the job's `technical` score (reused, not recomputed).
   - **Salary Fit**: if the agent captured a `salary_range`, score it against the candidate's salary expectation. Otherwise, if `salary_data.json` is configured, run the **local** tool once per company — `python salary_lookup.py "<Company>" --json` (add `--city "<City>"` when `practical.country` names one) — and score the index vs. baseline. If neither is available, Salary Fit is `N/A`.
   - **Remote Fit** = the agent's `remote_fit`; **Visa Fit** = the agent's `visa_fit`.
   - Composite `practical_fit = 0.40·Skill + 0.20·Salary + 0.20·Remote + 0.20·Visa`, dropping and renormalizing any `N/A` sub-score (no salary data → Skill 0.50 / Remote 0.25 / Visa 0.25). Round to an integer and map to the advisory band (Clear 70+, Workable 50-69, Friction 30-49, Blocked <30).
4. **Vetoes exclude from the shortlist, no matter either score** — list vetoed jobs separately with the reason:
   - Location `FAIL` (e.g. requires relocation).
   - Visa `VETO` (`practical.visa_veto: true` — sponsorship the candidate needs is explicitly excluded).
   Location `FLAG` (e.g. heavy travel) stays in the ranking but carries a visible ⚠ marker for the user to judge.
5. **Deadline urgency:** a deadline within 7 days gets a 🔥 marker and wins ties. A deadline that has already passed moves the job to `expired`.

Sort by the `--by` key (default `quality`) descending; the other score is the first tiebreaker and deadline urgency the second. Whichever key is primary, **both** the quality score and `practical_fit` appear in the output.

---

## Step 4: Update State

Update `job_scraper/seen_jobs.json` in place - these fields are additive to the scraper's schema:

- Ranked jobs: set `"status": "ranked"` and add `"rank_score": <overall quality>`, `"rank_verdict": "<band>"`, `"rank_date": "YYYY-MM-DD"`, and the ranking-layer fields `"practical_fit": <composite>`, `"practical_band": "<Clear|Workable|Friction|Blocked>"`, and `"practical_scores": { "skill": N, "salary": N | null, "remote": N, "visa": N }` (use `null` for an `N/A` sub-score).
- Visa-vetoed jobs: keep them out of the shortlist but still store their scores with `"practical_band": "Blocked"` so a re-run does not re-fetch them.
- Dead or past-deadline jobs: set `"status": "expired"`

Do not modify `job_search_tracker.csv` - that file records applications, and `/rank` never applies. Re-running `/rank` is idempotent: already-`ranked` jobs are skipped unless `--all` re-scores them.

---

## Step 5: Present the Shortlist

```
## Job Ranking - YYYY-MM-DD

Ranked <N> new postings (<X> shortlisted, <Y> below threshold, <Z> expired/vetoed). Sorted by <quality|practical>.

### Shortlist

| # | Fit | Verdict | Practical | Band | Title | Company | Location | Deadline | |
|---|-----|---------|-----------|------|-------|---------|----------|----------|---|
| 1 | 78 | Strong Fit | 82 | Clear | ... | ... | ... | ... | 🔥 |

### Why these ranked highest
**1. <Title> at <Company> — Fit 78 / Practical 82 (Clear)** - [2-3 strength bullets and the honest gap, from the agent's findings]. Practical-layer note: [salary/remote/visa signal, e.g. "salary N/A; remote-friendly; already authorized"].
[repeat for each shortlisted job]

### Below threshold
| Fit | Verdict | Practical | Title | Company | One-line reason |

### Excluded
- <Title> at <Company> - location FAIL: requires relocation
- <Title> at <Company> - visa VETO: posting states no sponsorship, candidate needs it
- <Title> at <Company> - expired <date>
```

The `Fit`/`Verdict` columns are the fit-quality score; `Practical`/`Band` are the ranking-layer score. Whichever `--by` key is primary, show both so the user sees good-role vs. can-I-take-it at a glance.

Rules for the presentation:

- Every claim traces to fetched posting text or the profile - no invented details.
- Say explicitly that these are **triage scores from the posting text plus a local salary lookup only** (no company research or web searches), and that `/apply` will re-evaluate with company research before anything is drafted.
- Then ask: "Want to apply to any of these? Give me the number(s) and I'll start with the full `/apply` workflow."
- If the user picks one, run the `/apply` workflow on that job's URL, passing the triage verdict as prior context but **re-running the full Step 1 evaluation** - triage never substitutes for it.

---

## Important Rules

1. **Never rank unfetched postings.** A job whose posting cannot be retrieved is marked expired, not guessed at.
2. **Triage depth only.** No company research, no web searches, no reviewer agents - `/rank` exists to be cheap enough to run on every scrape batch. The one exception is the **local, offline** `salary_lookup.py` tool, which feeds the ranking layer's Salary Fit; it makes no network calls and is skipped gracefully when `salary_data.json` is absent.
3. **Deal-breakers veto scores.** A 90-point job that fails a location deal-breaker or a visa deal-breaker is excluded, not ranked first - on either sort key.
4. **Honest scoring.** Gaps are reported per job; a low-scoring posting is presented as such. The score bands and weights come from `04-job-evaluation.md` - if the user disagrees with a ranking, the fix is updating their profile or the framework, not bending scores.
5. **State stays consistent.** `seen_jobs.json` fields are only added, never restructured, so `/scrape`'s dedup keeps working; the tracker is read-only for this command.
6. **Practical layer degrades honestly.** A missing reference value or missing salary data makes the relevant sub-score `N/A` (renormalized out of the composite), never a fabricated number. `practical_fit` is advisory and never overrides an explicit veto.
