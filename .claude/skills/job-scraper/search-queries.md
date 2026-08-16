# Search Queries for Job Scraper

<!-- SETUP: Customize these queries based on your skills, target roles, location, and workplace mode -->

## Search Sites

Primary (your market's job boards - scaffold one with `/add-portal`):
- **[YOUR_JOB_BOARD]** - your market's largest general job board
- **linkedin.com/jobs** - LinkedIn job listings (filter: [YOUR_COUNTRY] / [YOUR_CITY], plus remote when the Workplace filter says so)
- **[YOUR_INDUSTRY_JOB_BOARD]** - a niche/industry board for your field (optional)
- **[YOUR_ADDITIONAL_JOB_BOARD]** - another major board for your market (optional)

Secondary (company career pages via Google):
- Direct Google searches with `site:` filters for known target companies

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

## Query Categories

Queries are grouped by priority. How you combine them with geography depends on **Workplace filter → Mode**:

- **onsite / hybrid:** append location terms ([YOUR_CITY], [YOUR_REGION]) where the site supports it.
- **remote-only:** do **not** append city to keyword queries. Use the Portal remote flags above.
- **remote-ok:** run both a local commute pass (city terms) and a remote pass (remote flags, no city on Jobindex).

### Priority 1: [YOUR_PRIMARY_ROLE_TYPE]

These match your strongest and most desired career direction.

Local / onsite pass (skip when mode is `remote-only`):
```
site:[YOUR_JOB_BOARD] "[YOUR_PRIMARY_JOB_TITLE]" [YOUR_CITY]
site:[YOUR_JOB_BOARD] "[YOUR_KEY_SKILL]" [YOUR_CITY]
site:linkedin.com/jobs "[YOUR_PRIMARY_JOB_TITLE]" [YOUR_COUNTRY]
```

Remote pass (skip when mode is `onsite`):
```
site:[YOUR_JOB_BOARD] "[YOUR_PRIMARY_JOB_TITLE]" remote OR hjemmearbejde OR fjernarbejde
site:linkedin.com/jobs "[YOUR_PRIMARY_JOB_TITLE]" remote
```

### Priority 2: [YOUR_DOMAIN_EXPERTISE]

These match your domain expertise.

Local / onsite pass (skip when mode is `remote-only`):
```
site:[YOUR_JOB_BOARD] [YOUR_DOMAIN_KEYWORD_1] [YOUR_CITY] OR [YOUR_REGION]
site:[YOUR_JOB_BOARD] [YOUR_DOMAIN_KEYWORD_2] [YOUR_COUNTRY]
site:linkedin.com/jobs [YOUR_DOMAIN_KEYWORD_1] [YOUR_CITY] [YOUR_COUNTRY]
```

Remote pass (skip when mode is `onsite`):
```
site:[YOUR_JOB_BOARD] [YOUR_DOMAIN_KEYWORD_1] remote OR hjemmearbejde
site:linkedin.com/jobs [YOUR_DOMAIN_KEYWORD_1] remote
```

### Priority 3: [YOUR_ADJACENT_ROLE_TYPE]

Adjacent roles you could pivot into.

Local / onsite pass (skip when mode is `remote-only`):
```
site:[YOUR_JOB_BOARD] "[YOUR_ADJACENT_TITLE_1]" [YOUR_KEY_SKILL] [YOUR_CITY]
site:[YOUR_JOB_BOARD] "[YOUR_ADJACENT_TITLE_2]" [YOUR_KEY_SKILL] [YOUR_CITY]
```

Remote pass (skip when mode is `onsite`):
```
site:[YOUR_JOB_BOARD] "[YOUR_ADJACENT_TITLE_1]" [YOUR_KEY_SKILL] remote
```

### Priority 4: Broader Technical / Consulting

Wider net for general technical roles.

Local / onsite pass (skip when mode is `remote-only`):
```
site:[YOUR_JOB_BOARD] [YOUR_KEY_SKILL] developer [YOUR_CITY]
site:linkedin.com/jobs "[YOUR_KEY_SKILL] developer" [YOUR_CITY]
site:[YOUR_JOB_BOARD] "technical consultant" [YOUR_DOMAIN] [YOUR_CITY]
```

Remote pass (skip when mode is `onsite`):
```
site:[YOUR_JOB_BOARD] [YOUR_KEY_SKILL] developer remote
site:linkedin.com/jobs "[YOUR_KEY_SKILL] developer" remote
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

## Date Filter

Only include jobs posted within the last 14 days, or with an application deadline that has not yet passed. If a posting date cannot be determined, include it but flag as "date unknown".

## Adapting Queries

If the user specifies a focus area, select queries from the matching category and also generate 2-3 custom queries for that focus. For example:
- "/scrape [focus_area]" -> relevant category queries + custom focus-specific queries
- "/scrape remote" -> remote pass only, even if mode is `remote-ok`
