# Search Queries for Job Scraper

<!-- SETUP: Customize these queries based on your skills, target roles, location, and workplace mode -->

## Installed portal CLIs (primary for `/scrape`)

`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first. Shipped country-agnostic CLIs include `linkedin-search` and `freehire-search`; Danish demos and any skill you add with `/add-portal` are included the same way. You do **not** need a matching `site:` line below for those CLIs to run.

The `site:` query templates in this file are the **WebSearch fallback** — for portals without a CLI, company career pages, or when a CLI fails.

**Language scope:** write every query category in every language listed in your CLAUDE.md Languages table (typically 1-2, sometimes more). A posting requiring a language you have *not* declared, as a job condition, is excluded before scoring; a posting requiring a *higher level* than you declared in a language you *do* work in is flagged for your own judgment, not excluded — see `04-job-evaluation.md`'s Language Gate, the single source of truth for this rule. Translate each category's keywords rather than machine-translating word-for-word (e.g. "Frontend Developer" -> "Desarrollador Frontend", not a literal word-for-word translation) if you work in more than one language.

## Workplace filter

**Mode:** [YOUR_WORKPLACE_MODE]

One of: `onsite` | `hybrid` | `remote-ok` | `remote-only`.
`/setup` default when the user is open to remote but still wants local roles: `remote-ok`.

**Remote regions / timezones:** [YOUR_REMOTE_REGIONS]

Examples: `EU / CET`, `anywhere`, `US East`. Used to keep true-remote jobs whose HQ city string is overseas.

**Employer country constraint:** [YOUR_EMPLOYER_COUNTRY_CONSTRAINT]

Examples: `employer must be in Denmark`, `none`. This is a tax/contract constraint, not commute.

**Freehire region codes** (if using freehire-search): [YOUR_FREEHIRE_REGIONS]

Examples: `eu`, `us`, `none`. Always OR `none` on remote passes so unresolved-geo remotes are not dropped.

### Portal remote flags

When mode is `remote-only` or `remote-ok`, `/scrape` must pass each portal's **documented** remote flag. Never fake remote by stuffing a city into the query except where a portal has no flag (Jobindex keyword pass).

| Portal | Remote search | Do not |
|--------|---------------|--------|
| linkedin-search | `-l "Remote" --remote remote` (global); optional second pass `-l "[YOUR_CITY]" --remote remote` (remote in this market) | city as `-l` without `--remote` |
| freehire-search | `--remote remote --region [YOUR_FREEHIRE_REGIONS],none` | `--region` without `none` (drops unresolved-geo remotes) |
| jobbank-search | `--remote helt` (`delvist` if hybrid) | city-only search for a remote-only profile |
| jobindex-search | no API filter; keyword pass `remote` / `hjemmearbejde` **without** city in `--query`; classify from `detail` | appending `[YOUR_CITY]` to remote queries |
| jobnet-search / jobdanmark-search | no search-time remote flag; post-filter from location/description after `detail` | treating HQ city as onsite when the description says fully remote |

## Search Sites

Primary (your market's job boards - scaffold one with `/add-portal`):
- **[YOUR_JOB_BOARD]** - your market's largest general job board
- **linkedin.com/jobs** - LinkedIn job listings (filter: [YOUR_COUNTRY] / [YOUR_CITY], plus remote when the Workplace filter says so); also covered by `linkedin-search` CLI
- **[YOUR_INDUSTRY_JOB_BOARD]** - a niche/industry board for your field (optional)
- **[YOUR_ADDITIONAL_JOB_BOARD]** - another major board for your market (optional)

Secondary (company career pages via Google):
- Direct Google searches with `site:` filters for known target companies

## Query Categories

Queries are grouped by priority. Write **each category in every language from your Languages table** (see Language scope above). How you combine them with geography depends on **Workplace filter → Mode**:

- **onsite / hybrid:** append location terms ([YOUR_CITY], [YOUR_REGION]) where the site supports it.
- **remote-only:** do **not** append city to keyword queries. Use the Portal remote flags above.
- **remote-ok:** run both a local commute pass (city terms) and a remote pass (remote flags, no city on Jobindex).

**Organize by function, not job title.** The same underlying work carries different titles across companies and markets (a "Data Scientist" role at one employer may be posted as "Insights Analyst" or "Data Consultant" at another). Name each priority category after the function it covers, and list several plausible job titles as query variants within that category rather than betting an entire priority tier on one exact title string.

### Priority 1: [YOUR_PRIMARY_ROLE_TYPE]

These match your strongest and most desired career direction.

Local / onsite pass (skip when mode is `remote-only`):
```
site:[YOUR_JOB_BOARD] "[YOUR_PRIMARY_JOB_TITLE_1]" [YOUR_CITY]
site:[YOUR_JOB_BOARD] "[YOUR_PRIMARY_JOB_TITLE_2]" [YOUR_CITY]
site:[YOUR_JOB_BOARD] "[YOUR_KEY_SKILL]" [YOUR_CITY]
site:linkedin.com/jobs "[YOUR_PRIMARY_JOB_TITLE_1]" [YOUR_COUNTRY]
```

Remote pass (skip when mode is `onsite`):
```
site:[YOUR_JOB_BOARD] "[YOUR_PRIMARY_JOB_TITLE_1]" remote OR hjemmearbejde OR fjernarbejde
site:linkedin.com/jobs "[YOUR_PRIMARY_JOB_TITLE_1]" remote
```

### Priority 2: [YOUR_DOMAIN_EXPERTISE]

These match your domain expertise.

```
site:[YOUR_JOB_BOARD] [YOUR_DOMAIN_KEYWORD_1] [YOUR_CITY] OR [YOUR_REGION]
site:[YOUR_JOB_BOARD] [YOUR_DOMAIN_KEYWORD_2] [YOUR_COUNTRY]
site:linkedin.com/jobs [YOUR_DOMAIN_KEYWORD_1] [YOUR_CITY] [YOUR_COUNTRY]
```

### Priority 3: [YOUR_ADJACENT_ROLE_TYPE]

Adjacent roles you could pivot into.

```
site:[YOUR_JOB_BOARD] "[YOUR_ADJACENT_TITLE_1]" [YOUR_KEY_SKILL] [YOUR_CITY]
site:[YOUR_JOB_BOARD] "[YOUR_ADJACENT_TITLE_2]" [YOUR_KEY_SKILL] [YOUR_CITY]
```

### Priority 4: Broader Technical / Consulting

Wider net for general technical roles.

```
site:[YOUR_JOB_BOARD] [YOUR_KEY_SKILL] developer [YOUR_CITY]
site:linkedin.com/jobs "[YOUR_KEY_SKILL] developer" [YOUR_CITY]
site:[YOUR_JOB_BOARD] "technical consultant" [YOUR_DOMAIN] [YOUR_CITY]
```

## Location Filter

**Onsite and hybrid jobs:** verify the office location is within reasonable commute distance from your home. Define acceptable areas:
- [YOUR_CITY] and surrounding areas
- [ACCEPTABLE_AREA_1]
- [ACCEPTABLE_AREA_2]
- [BORDERLINE_AREA] (borderline - ~X min by transit)
- [TOO_FAR_AREA] (too far)

**Remote jobs:** do **not** apply the commute tiers above. Keep the job if it matches **Remote regions / timezones** and **Employer country constraint**. An HQ city in another country is not a relocation if the posting is truly remote.

**Fake remote:** skip (or flag for `/rank` to FAIL) if the title says remote but the posting requires relocation or a specific office 5 days a week.

## Language Filter

Your working languages and levels are in CLAUDE.md's Languages table. When filtering scraped results, apply `04-job-evaluation.md`'s Language Gate: a posting requiring a language you haven't declared at all is excluded; a posting requiring a higher level than you declared in a language you do work in is not excluded, flag it clearly instead (see `job-scraper/SKILL.md`'s Step 3 "Quick Fit Assessment" for how the flag surfaces in `/scrape` output). Postings simply *written* in a language you don't work in, that don't require it on the job, are fine.

## Date Filter

Only include jobs posted within the last 14 days, or with an application deadline that has not yet passed. If a posting date cannot be determined, include it but flag as "date unknown".

## Adapting Queries

If the user specifies a focus area, select queries from the matching category and also generate 2-3 custom queries for that focus. For example:
- "/scrape remote" -> remote pass only, even if mode is `remote-ok`
- "/scrape [focus_area]" -> relevant category queries + custom focus-specific queries
