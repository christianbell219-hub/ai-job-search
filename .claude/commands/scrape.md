# /scrape - Find new job postings

You are running the job-scraper skill. **Do not fork this spec.** Follow `.claude/skills/job-scraper/SKILL.md` exactly (portal `enabled:` flags, seen_jobs dedup, open-positions only).

`$ARGUMENTS` may contain a focus area (`/scrape data science`), `broad`, or `remote`.

When the user picks a result, run the full `/apply` workflow on that URL — not the job-application-assistant skill shortcut. Do not write `job_search_tracker.csv` from this command.
