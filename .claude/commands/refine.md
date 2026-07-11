# /refine - Learn From What Converts and Sharpen the Search

You are running the feedback loop that makes the search smarter as real results come in. `/refine` learns from **outcomes**, not from what the user merely applied to: an application that reached interviews or an offer is strong evidence the role type fits; a rejection or silence is evidence against. It distills those resolved outcomes into a model and proposes sharper `/scrape` queries pointed at what actually works.

**It waits for outcomes by design.** Until the user has recorded a handful of resolved applications (interviews, offers, rejections) with `/outcome`, there is nothing to learn from and this command says so and stops. That is intentional - it never refines on applications that are still pending.

**Discipline (mirrors `/outcome` → `/setup`):** this command *builds and persists the model* and *proposes* query changes, but only rewrites `search-queries.md` with the user's explicit approval. It never fabricates preferences and never edits profile skill files silently.

Follow these steps **in order**.

---

## Step 0: Parse Input

`$ARGUMENTS` may contain:

- Nothing → build the model, persist it, and (if ready) propose query changes for approval.
- `--show` → build and print the model only; propose nothing and write nothing.
- `--min <N>` → override how many resolved outcomes are required before refining (default 3).
- `--focus <area>` → bias the proposed queries toward a direction the user names (still grounded in the model).

---

## Step 1: Build the Outcome-Driven Model

Run the deterministic engine (local, read-only, stdlib):

```bash
python3 tools/preference_model.py --json           # add --min-outcomes N to match --min
```

It reads `job_search_tracker.csv` and classifies each application's `status` (the column `/outcome` maintains): interviews and offers are positive signal, rejections/no-response negative, and anything still `applied`/`in_progress` is **pending** and contributes nothing. It returns:

- `ready` (bool) and `signal_strength` (`low`/`medium`/`high`)
- `counts` - applications, resolved, pending, interviews+, rejected, no-response
- `liked.roles` / `liked.companies` / `liked.sectors` - what has been converting
- `disliked.roles` - what stalls (rejected/ignored)

Do not recompute these weights yourself - the tool owns the arithmetic. Your job is interpretation.

---

## Step 2: If Not Ready, Wait

If `ready` is `false`, tell the user plainly how many resolved outcomes they have versus the threshold, and stop without proposing or writing query changes:

> "Waiting for outcomes - you have <resolved> of <min> resolved applications. Record what happens to your applications with `/outcome` (interviews, offers, rejections). Once a few resolve, `/refine` will point your search at the role types that actually convert."

Still write the model snapshot to `preferences.json` (Step 3) so the pending/resolved counts are tracked over time, then stop. Do **not** touch `search-queries.md`.

---

## Step 3: Persist the Model

Write the model to `job_scraper/preferences.json` (personal data - already gitignored). This file is **additive and historical**: keep a short `history` array so the user can see how their conversion pattern shifts as more outcomes land.

```json
{
  "updated": "YYYY-MM-DD",
  "ready": true,
  "signal_strength": "low | medium | high",
  "counts": { "applications": N, "resolved": N, "pending": N, "interviews_plus": N, "rejected": N, "no_response": N },
  "liked": { "roles": [...], "companies": [...], "sectors": [...] },
  "disliked": { "roles": [...] },
  "history": [
    { "date": "YYYY-MM-DD", "resolved": N, "top_converting_roles": ["...", "..."], "note": "what shifted since last run" }
  ]
}
```

On re-run, append a new `history` entry (never rewrite past ones) and refresh the top-level fields. Idempotent within a day: update today's entry rather than duplicating it.

---

## Step 4: Propose Sharper Queries (approval required, ready only)

Only if `ready` is `true`. Read `.claude/skills/job-scraper/search-queries.md` and `.claude/skills/job-application-assistant/01-candidate-profile.md` (for current target roles and location terms). Then propose **additive** changes, grounded strictly in the model:

1. **Amplify what converts** - for the strongest `liked.roles`/`sectors`/`companies`, propose new query lines in the matching priority block (reuse the file's existing site/flag format - do not invent portal syntax).
2. **Reprioritize** - if a converting direction consistently outweighs a current Priority 1 that never converts, suggest swapping the priority order.
3. **De-emphasize what stalls** - for strong `disliked.roles` (repeatedly rejected/ignored), suggest dropping or narrowing those queries. Only on a clear pattern (multiple negative outcomes), never a single rejection.
4. **Adjacency (the "find more like what worked" step)** - propose 1-3 *new* role directions adjacent to what has been converting but not yet in the queries, with the reasoning from the model.

Present the proposal as a diff-style list grouped by priority block, then ask:

> **Apply these query changes?** Reply **yes** to apply all, or list the numbers to skip. These only add/adjust search queries - your profile and history are untouched.

Wait for the response. Apply only confirmed items to `search-queries.md` with the Edit tool. On `--show`, skip this step.

---

## Step 5: Confirm and Hand Off

Summarize:

> **Search refined from <resolved> resolved outcomes (signal: <strength>).**
> - Model saved to `job_scraper/preferences.json`
> - Applied: <query changes, or "none - still waiting for outcomes" / "none - directional only">
> - Converting: <top 3 role terms>; stalling: <top disliked, if any>
>
> Run `/scrape` to pull a fresh batch against the sharpened queries. As more applications resolve, this keeps getting sharper.

---

## Important Rules

1. **Outcomes, not applications.** `/refine` learns only from resolved results (interview/offer/rejection/no-response). Pending applications contribute nothing - the loop waits until real signal exists.
2. **Propose, don't impose.** Query changes to `search-queries.md` always require explicit approval. The model file accumulates automatically; the search strategy never changes silently.
3. **Honor the wait-gate.** Below `min_outcomes` resolved, produce no query changes - only the "waiting for outcomes" message and the tracked snapshot.
4. **Additive and honest.** Never fabricate a preference the model does not show. `preferences.json` history is append-only. `search-queries.md` edits reuse its existing format and never touch profile files.
5. **The tool owns the math.** Weights and rankings come from `tools/preference_model.py`; this command interprets and synthesizes, it does not re-derive scores.
