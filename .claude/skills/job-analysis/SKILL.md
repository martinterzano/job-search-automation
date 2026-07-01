---
name: job-analysis
description: Analyzes a raw job posting, extracts skills classified as Must/Should/Nice, and calculates a fit score against the candidate profile. Use when receiving a new job offer to evaluate.
disable-model-invocation: true
argument-hint: "[company] [role]"
allowed-tools: Read, Write, Bash(python *)
---

# Job Analysis

## When to use this skill
Invoke with `/job-analysis [company] [role]` when you receive a new job posting.
Requires the job text to be available (pasted in chat or saved in `jobs_inbox/`).

## Required inputs
- Raw job posting text (pasted directly or as a file in `jobs_inbox/`)
- `profile.json` at the project root (candidate profile)

## Execution sequence

### Step 1 — Parse the posting
If the posting comes as text in chat, save it first to `jobs_inbox/{company}_{role}.txt`.

```bash
python .claude/skills/job-analysis/scripts/parse_job_posting.py jobs_inbox/{company}_{role}.txt
```

Output: `jobs_parsed/{company}_{role}_{date}.json`

### Step 2 — Extract and classify skills + experience requirements

Save extract_skills output to `.tmp/` (create directory if it doesn't exist):

```bash
PYTHONIOENCODING=utf-8 python .claude/skills/job-analysis/scripts/extract_skills.py jobs_parsed/{company}_{role}_{date}.json > .tmp/{stem}_skills.json
```

where `{stem}` = `{company}_{role}` (without date).

**Mandatory output review**: the script classifies by keyword matching and positional heuristics, which produces noise. Read `.tmp/{stem}_skills.json` and correct before continuing:

1. **False `must`**: skills appearing in sections labeled "stand out", "nice to have", "plus", "desirable" → move them to `nice`. The script's heuristic marks them as `must` by position.
2. **Company skills, not candidate skills**: skills mentioned in the company description or sector context (not as candidate requirements) → remove from classification.
3. **Non-technical requirements**: manually add to the corresponding fields requirements the script doesn't capture:
   - Domain experience (e.g., "background in regulated banking", "experience in healthcare sector")
   - Project participation requirements (e.g., "leading digital transformation projects")
   - Domain requirements (e.g., "DAMA certification", "HL7/FHIR standards")
   - Implicit seniority (e.g., "5+ years of ML experience in production")
4. **Overwrite** `.tmp/{stem}_skills.json` with the corrected version.

Also build the separate `experience_requirements` field:
- `experience_requirements.must`: entry barriers — experience or context without which the candidate is not considered
- `experience_requirements.should`: valued positively but not eliminatory

### Step 3 — Calculate fit score

```bash
python .claude/skills/job-analysis/scripts/calculate_fit_score.py .tmp/{stem}_skills.json profile.json
```

where `{stem}` = `{company}_{role}` (same file saved in Step 2).

Output: mechanical `fit_score` 0–100, `role_type`, role_type thresholds, critical gaps, strengths, provisional recommendation (`apply` / `conditional` / `skip`). Claude adjusts the score in Step 4.

Differentiated thresholds applied automatically:
- `data_scientist` / `default`: apply≥65, conditional≥50
- `ml_engineer`: apply≥63, conditional≥48
- `ai_engineer`: apply≥60, conditional≥45
- `analytics`: apply≥70, conditional≥55

### Step 3.5 — Enrich with candidate context
Before writing the final analysis, read:
- `assets/knowledge_base/project_depth.md` — to evaluate real fit using the precise technical description of each project (architecture, metrics, real industries)
- `assets/knowledge_base/self_framing.md` — to understand which gaps are honest (e.g., "has space to improve", "actively learning") and not overestimate capabilities

Use this context to:
- Adjust gap analysis with precision (does the candidate actually have experience in X, or is it learning_in_progress?)
- Enrich the `interpretation` field with the candidate's honest perspective on their own profile
- Identify if the candidate's real industries (documented in profile.json) are relevant to the role

### Step 3.7 — Determine salary range

Determine two salary fields:

**`salary`** — capture verbatim what the posting mentions. Leave empty if the posting doesn't explicitly publish a salary. Don't invent or estimate here.

**`salary_target`** — the range the candidate should ask for, being conservative/mid. Independent of what the posting says. Useful for negotiation. Always complete this field.

Logic for `salary_target`:
- Consider: job title + seniority level + location + company type (startup, scale-up, consultancy, corporation)
- Use market data appropriate to the target market (configure market ranges for your geography in this SKILL.md)
- Aim for the **lower-to-mid third** of the total market range for the candidate profile (conservative but not minimum)
- Format: `"~XX,000–YY,000 {CURRENCY}/year (conservative/mid target)"`

> **Configure your market**: Replace the example ranges below with ranges appropriate for your target market and currency. The candidate's `profile.json` should include `preferences.currency` and `preferences.min_salary`.

Example ranges (adjust to your market):
- Junior DS (0–2 years): market ~$80K–$110K → target `~$85K–$100K/year`
- Mid DS (2–5 years): market ~$110K–$150K → target `~$115K–$135K/year`
- Senior DS (5+ years): market ~$150K–$200K → target `~$155K–$180K/year`
- Lead / Principal DS: market ~$180K–$250K+ → target `~$185K–$220K/year`

**`salary_range`** — keep for backward compatibility. Same value as `salary_target`.

### Step 3.8 — Sponsorship check (if applicable)

If `profile.json` includes `"preferences": { "sponsorship_required": true }`:

- Check the posting for explicit sponsorship signals
- If posting says "no sponsorship" / "must be authorized to work" / "US citizen or permanent resident only" → force `recommendation: skip`, add note to `interpretation`: "No sponsorship offered. Candidate requires visa sponsorship."
- If posting mentions "visa sponsorship provided" / "sponsorship available" → note positively in `interpretation`
- If posting is silent on sponsorship → note in `interpretation`: "Sponsorship not mentioned — verify before applying."

### Step 4 — Reasoning + Score adjustment + Consolidate and save

**Before writing the JSON**, Claude reasons qualitatively and adjusts the mechanical score.

#### Single score system with qualitative adjustment

`calculate_fit_score.py` returns a mechanical score based on keyword matching and aliases. Claude adjusts it applying the rules in this section and produces the final `fit_score` in the JSON.

`fit_score_final` = `mechanical_score` + sum of adjustments

**Bounds:**
- Each individual adjustment: **maximum ±8 points**
- Total accumulated adjustment: **maximum ±20 points** over the mechanical score
- The final `fit_score` is always between 0 and 100

The mechanical score appears in internal reasoning but not as a separate field in the JSON. The JSON's `fit_score` is always the adjusted one.

---

#### Forced override — BEFORE score calculation

0. **Published salary below minimum threshold**: If the posting explicitly publishes a salary (non-empty `salary` field) and that salary is **below the candidate's `preferences.min_salary`** in profile.json, force `recommendation: skip` regardless of technical score. Adjustment: −20 pts. Record in `interpretation`: "Published salary below candidate's minimum threshold." **Do not continue with cv-adaptation or cover-letter.**

   - Applies only when salary is explicitly published in the posting. If no salary is mentioned, skip this rule.
   - Applies to the upper end of the range if a range is published.

---

#### Downward adjustment rules

1. **Hard domain barrier**: The role requires sector experience without which the candidate is not considered (appears in `experience_requirements.must`). → `recommendation: skip` regardless of score. Adjustment: −8 pts.

2. **Gaps in `experience_requirements.must`**: Significant domain requirements the candidate doesn't meet (e.g., "5+ years in regulated banking", "required DAMA certification"). Adjustment: −4 to −8 pts depending on severity.

3. **Reporting-centric roles**: The central focus of the role is reporting, dashboards, or BI analytics without a substantial predictive ML component. Signals: "reporting" in the title, or reporting/visualization is the first and main responsibility without modeling. If it doesn't include advanced analytics / predictive modeling / ML as a relevant component → −8 pts.

4. **"Stand out" skills ≠ hard gaps**: Skills in "nice to have", "plus", "desirable", "stand out", "valuable" sections do NOT penalize the score. Classify them in `skills.nice`.

---

#### Upward adjustment rules

5. **Sector match** (+5 to +8 pts): The candidate has documented experience in the same sector as the role. Verify in `project_depth.md` — only with a real project backing. Use the sectors documented in profile.json experience.

6. **Cloud platform + production** (+5 to +8 pts): The role requires the candidate's primary cloud platform (from profile.json) centrally, and the candidate has models in production on that stack.

7. **MLOps end-to-end** (+4 to +6 pts): The role emphasizes deployment and production pipelines. The candidate has production models with automated pipelines and out-of-time validation. **Do not accumulate with cloud bonus if they represent the same differential.**

8. **LLM / Agentic for AI Engineer roles** (+5 to +8 pts): `role_type: ai_engineer` + LLM APIs/RAG/agentic in `skills.must` + the candidate has real documented experience.

---

#### Adjustment process

1. Read the mechanical score from `calculate_fit_score.py` output.
2. Identify which rules apply and calculate each adjustment (max ±8 per rule).
3. Sum adjustments → truncate if it exceeds ±20.
4. `fit_score` final = mechanical score + total adjustment (rounded to 1 decimal).
5. **Final recommendation**: reflect complete reasoning using the adjusted `fit_score` and `role_type` thresholds. If there's a hard domain barrier → `skip` even if the adjusted score is high.

6. **Interpretation**: 2-3 sentences. Mention what works well, what doesn't, and whether the score was adjusted and why.

Save to `outputs/ready/{company}_{role}/analysis.json` (create directory if it doesn't exist):

```json
{
  "company": "string",
  "role": "string",
  "role_type": "data_scientist | ml_engineer | ai_engineer | analytics | default",
  "date_processed": "YYYY-MM-DD",
  "location": "string",
  "salary": "string (verbatim from posting; empty if not published)",
  "salary_target": "string (~XX,000–YY,000 {CURRENCY}/year conservative/mid target)",
  "salary_range": "string (same as salary_target; kept for compatibility)",
  "modality": "string",
  "skills": { "must": [], "should": [], "nice": [] },
  "experience_requirements": { "must": [], "should": [] },
  "fit_score": 0,
  "gaps": { "must": [], "should": [] },
  "strengths": [],
  "recommendation": "apply | skip | conditional",
  "interpretation": "string — qualitative fit reasoning; mention adjustment applied if it differs from mechanical score",
  "company_summary": "string — 1–2 sentences: what the company does, sector, size/stage if mentioned",
  "role_summary": "string — 1–2 sentences: core role responsibilities and main tech stack",
  "prescreening": {
    "company_type": "product_company | consultora_ds | staff_augmentation | startup_early | corporate | unknown",
    "role_core": "ml_modeling | analytics_bi | product_ds | mlops_engineering | research | mixed",
    "seniority_required": "junior | mid | senior | lead",
    "stack_gaps": ["pytorch_dl_must | ab_testing_core | databricks_must | computer_vision_must | spark_scala_must"],
    "domain": "fintech | insurtech | healthtech | saas | retail | esg | consulting_ds | pharma | gaming | logistics | industrial | adtech | academic | media | services_generic | other"
  },
  "summary": "string",
  "batch_date": "YYYY-MM-DD | null — date the .txt was saved (file mtime)",
  "days_posted": "integer | null — days since publication until the batch (0 if < 1 day)",
  "days_posted_raw": "string | null — original text e.g. 'posted 6 days ago', '3 hours ago'",
  "applicants_count": "integer | null — number of applicants at the time of batch",
  "applicants_label": "string | null — original label e.g. '60' or 'Over 100'"
}
```

**Note on metadata fields**: these fields are extracted automatically by `parse_job_posting.py` from the raw posting text. They'll be available in `jobs_parsed/*.json`. Copy them directly to `analysis.json` without modification.

Log result to `logs/job_analysis.log`.

## Error handling

| Error | Action |
|---|---|
| Badly formatted posting or unrecognizable fields | Ask user to clean up the text |
| Unrecognized skills in the taxonomy | Add to `.tmp/unknown_skills.txt` for review |
| `profile.json` not found | Stop and request the file |
| `recommendation: skip` | Inform user and do not continue with cv-adaptation |

## Edge cases
- Postings in languages other than English: the parser auto-detects language
- Hybrid roles (DS + Engineering): classify under the dominant role
- Postings without explicit tech stack: mark `skills.must` as `["stack not specified"]`

## Output validations
- `fit_score` between 0 and 100 (mechanical score + qualitative adjustment ±20)
- `skills.must` with at least 1 element
- `recommendation` only accepts: `apply`, `skip`, `conditional`

## Scripts available
- [`scripts/parse_job_posting.py`](scripts/parse_job_posting.py) — parse and structure raw text
- [`scripts/extract_skills.py`](scripts/extract_skills.py) — extract and classify skills; detects `role_type` and returns differentiated `recommended_thresholds` by role type
- [`scripts/calculate_fit_score.py`](scripts/calculate_fit_score.py) — weighted mechanical score (Must 65% / Should 25% / Nice 10%) with conservative semantic aliases and differentiated thresholds by `role_type`; Claude adjusts ±20 pts in Step 4 to produce the final `fit_score`
