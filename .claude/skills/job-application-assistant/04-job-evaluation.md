# Job Evaluation Framework

<!-- SETUP: Skill match areas and career goals are personalized by running /setup -->

## Scoring Dimensions

Evaluate each job posting against these five dimensions:

### 1. Technical Skills Match (0-100)
How well do the required/preferred skills align with the candidate's capabilities?

| Score | Meaning |
|-------|---------|
| 80-100 | Core requirements are primary skills |
| 60-79 | Most requirements match, 1-2 gaps that are learnable |
| 40-59 | Partial match, significant upskilling needed |
| 0-39 | Fundamental mismatch |

**Strong match areas:** [YOUR_PRIMARY_SKILLS]
**Moderate match areas:** [YOUR_SECONDARY_SKILLS]
**Weak match areas:** [SKILLS_YOU_LACK]

### 2. Experience Match (0-100)
Does work history align with what they're looking for?

| Score | Meaning |
|-------|---------|
| 80-100 | Direct experience in the same domain and role type |
| 60-79 | Related experience, transferable skills clear |
| 40-59 | Adjacent experience, would need to make the case |
| 0-39 | Unrelated experience |

**Strong:** [YOUR_DIRECT_EXPERIENCE_DOMAINS]
**Moderate:** [YOUR_ADJACENT_EXPERIENCE]
**Entry-level:** [ROLES_WITH_LIMITED_EXPERIENCE]

### 3. Behavioral/Culture Fit (0-100)
Does the role and company culture match the behavioral profile?

| Score | Meaning |
|-------|---------|
| 80-100 | Culture strongly matches behavioral preferences |
| 60-79 | Mixed signals but mostly compatible |
| 40-59 | Some friction areas |
| 0-39 | Significant culture mismatch |

**Red flags to research:** Department disorganization, work dominated by maintenance over development, poor chemistry with leadership, culture mismatches. Check reviews, media coverage, LinkedIn connections, and network contacts for insider perspective.

### 4. Location & Logistics (Pass/Fail + Notes)
- Within commute range: PASS
- Remote with occasional office: PASS
- Requires relocation: FAIL (deal-breaker)
- Frequent international travel: FLAG (discuss with user)

### 5. Career Alignment & Motivation (0-100)
Does this role advance career goals and contain tasks that energize?

| Score | Meaning |
|-------|---------|
| 80-100 | Strongly aligned with career direction, clear growth path |
| 60-79 | Good role but only partially aligned with long-term goals |
| 40-59 | Decent job but doesn't build toward career goals |
| 0-39 | Dead end or backwards step |

**Career goals:**
- [YOUR_CAREER_GOAL_1]
- [YOUR_CAREER_GOAL_2]
- [YOUR_CAREER_GOAL_3]

**Motivation filter:** Evaluate not just whether you *can* do the tasks, but whether the tasks will *energize* you. Consider:
- Tasks that energize: [YOUR_ENERGIZING_TASKS]
- Tasks that drain: [YOUR_DRAINING_TASKS]
- Non-task factors: leadership style, department culture, company values, degree of autonomy

**Life situation alignment:** Consider personal constraints:
- **Security**: [YOUR_FINANCIAL_SITUATION_CONTEXT]
- **Flexibility**: [YOUR_SCHEDULE_CONSTRAINTS]
- **Professional development**: [YOUR_GROWTH_PRIORITIES]

### 6. Salary Benchmark (Optional)

If the salary lookup tool is configured (`salary_data.json` exists), look up the company:
```
python salary_lookup.py "<Company Name>" --json
```

If a city is known from the posting, add `--city "<City>"` to narrow results.

Present findings as:
```
### Salary Benchmark
| Metric | Value |
|--------|-------|
| [Category] index | XX.X (+/-X.X% vs baseline) |
| Overall index | XX.X (+/-X.X% vs baseline) |
```

Interpret results relative to the baseline defined in the data file's metadata. For index-based data, higher typically means above-market compensation.

If the salary tool is not configured, skip this section.

## Practical Fit Ranking Layer

The six dimensions above measure *how good* a match the role is. This layer scores four **practical constraints** that decide whether a strong-looking role is actually pursuable: **Salary**, **Remote fit**, **Visa fit**, and **Skill match**. `/rank` computes it for every posting to rank a scrape batch; `/apply` Step 1 reports it too. It is built from the posting text plus the candidate reference values below — cheap enough to run in batch, with no company research or web searches.

**Candidate reference values** (populated by `/setup`; see also the "Work Preferences" section of `01-candidate-profile.md`):
- **Salary expectation:** [YOUR_SALARY_EXPECTATION] <!-- e.g. "min 550k DKK/yr, target 620k" or "at/above market for a senior role in [city]" -->
- **Remote preference:** [YOUR_REMOTE_PREFERENCE] <!-- one of: remote-only / hybrid-preferred / onsite-ok / flexible, plus the max acceptable commute -->
- **Work authorization:** [YOUR_WORK_AUTHORIZATION] <!-- e.g. "EU citizen, no sponsorship needed" or "needs visa sponsorship outside [region]" -->

If a reference value is still an unfilled placeholder, treat that sub-score as `N/A` (not zero) and say so — never invent the candidate's constraints.

### L1. Skill Match (0-100)
Reuse the **Technical Skills Match** score from dimension 1 — do not compute a second, divergent skill number. This axis exists so the ranking layer always shows the skill signal beside the logistics signals.

### L2. Salary Fit (0-100 or N/A)
| Score | Meaning |
|-------|---------|
| 80-100 | Stated or benchmarked pay meets or beats the target |
| 60-79 | At or just below target; negotiable |
| 40-59 | Noticeably below target |
| 0-39 | Well below the stated minimum (a soft deal-breaker — flag it) |

Sources, in priority order:
1. A salary range **in the posting** → compare to the candidate's expectation.
2. Otherwise, if `salary_data.json` is configured, the company's index vs. baseline from `python salary_lookup.py "<Company>" --json` (add `--city "<City>"` when the posting names one). An index above baseline scores higher.
3. Neither available → `N/A`.

### L3. Remote Fit (0-100)
Match the posting's work model against the candidate's remote preference and commute range.
| Score | Meaning |
|-------|---------|
| 80-100 | Work model matches preference (remote role for a remote-only candidate; onsite within easy commute) |
| 60-79 | Workable with minor friction (hybrid when the candidate wanted remote; onsite at the edge of commute range) |
| 40-59 | Significant friction (mostly onsite for a remote-preferring candidate) |
| 0-39 | Effectively incompatible (daily onsite far outside commute for a remote-only candidate) |

This complements the pass/fail **Location** dimension: Location vetoes on relocation; Remote Fit grades the day-to-day arrangement.

### L4. Visa / Work-Authorization Fit (0-100, veto-capable)
| Score | Meaning |
|-------|---------|
| 100 | Candidate is already authorized to work in the job's country; no sponsorship needed |
| 60-79 | Sponsorship needed **and** the posting states sponsorship is available |
| 30-59 | Sponsorship needed; posting silent — an open question to confirm |
| 0 + **VETO** | Sponsorship needed **and** the posting explicitly rules it out |

A `VETO` excludes the job from the shortlist exactly like a Location `FAIL`, and is listed separately with the reason.

### Composite: `practical_fit`
Weighted mean of the available sub-scores:

`practical_fit = 0.40·Skill + 0.20·Salary + 0.20·Remote + 0.20·Visa`

When a sub-score is `N/A` (typically Salary), drop it and renormalize the remaining weights to sum to 1 (with no salary data: Skill 0.50, Remote 0.25, Visa 0.25). Round to the nearest integer. A Visa `VETO` overrides the number — the job is excluded regardless of `practical_fit`.

Advisory bands (separate from the fit-quality thresholds below):
- **Clear** (70+): no practical blockers
- **Workable** (50-69): minor friction to raise with the user
- **Friction** (30-49): real obstacles; pursue only with reason
- **Blocked** (<30 or VETO): a practical deal-breaker

The fit-quality score answers "is this a good role for me?"; `practical_fit` answers "can I actually take it?". Keep both visible — a Strong Fit role that is Blocked on visa is not a top pick.

## Output Format

Present the evaluation as:

```
## Job Fit Evaluation: [Role] at [Company]

| Dimension | Score | Notes |
|-----------|-------|-------|
| Technical Skills | XX/100 | [brief note] |
| Experience Match | XX/100 | [brief note] |
| Behavioral Fit | XX/100 | [brief note] |
| Location | PASS/FAIL | [brief note] |
| Career Alignment | XX/100 | [brief note] |

**Overall Score: XX/100** (weighted average of scored dimensions)

#### Practical Fit Ranking Layer
| Axis | Score | Notes |
|------|-------|-------|
| Skill Match | XX/100 | [same as Technical Skills above] |
| Salary Fit | XX/100 or N/A | [source: posting range / benchmark index / unavailable] |
| Remote Fit | XX/100 | [work model vs. preference] |
| Visa Fit | XX/100 or VETO | [authorization status] |

**Practical Fit: XX/100** [Clear / Workable / Friction / Blocked]

### Verdict: [Strong Fit / Good Fit / Moderate Fit / Weak Fit / Poor Fit]

### Key Strengths for This Role
- [bullet points]

### Gaps to Address
- [bullet points]

### Recommendation
[1-2 sentences: apply/skip/apply with caveats]

### Company Research Checklist
- [ ] Checked company website (mission, values, recent news)
- [ ] Checked review sites (Glassdoor, Jobindex, etc.)
- [ ] Checked LinkedIn for team size, recent hires, connections
- [ ] Checked media for restructuring, growth, or workplace issues
- [ ] Identified network contacts who may know the team/manager
```

## Weighting
- Technical Skills: 30%
- Experience Match: 25%
- Behavioral Fit: 15%
- Career Alignment: 30%

(Location is pass/fail, not weighted)

## Thresholds
- **Strong Fit** (75+): Definitely apply, tailor everything
- **Good Fit** (60-74): Apply, address gaps in cover letter
- **Moderate Fit** (45-59): Consider carefully, discuss with user
- **Weak Fit** (30-44): Probably skip unless strategic reasons
- **Poor Fit** (<30): Skip

## Pre-Application: Call the Employer (Best Practice)

Before writing the application, consider whether the candidate should call the contact person listed in the posting. **Only call if there are substantive questions** - never call just to "be remembered."

### When to Suggest Calling
- The posting has unclear or ambiguous requirements
- It's unclear which competencies are essential vs. nice-to-have
- The role description is vague about day-to-day tasks
- There's a named contact person who invites questions

### Good Questions to Ask
- "What are the primary challenges in this role?"
- "How is time typically divided across the listed responsibilities?"
- "Which competencies are most critical for success in this position?"
- "What does success look like in the first 6-12 months?"

### Rules for the Call
- Prepare a 30-second "elevator pitch" about your background in case they ask
- The call's purpose is **gathering information**, not delivering a pitch
- Take notes - use what you learn to tailor the application
- Reference the conversation naturally in the cover letter ("After speaking with [name], I was especially drawn to...")
