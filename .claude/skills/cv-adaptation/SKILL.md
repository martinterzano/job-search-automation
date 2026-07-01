---
name: cv-adaptation
description: Adapts the base CV for a specific job posting, prioritizing experiences and skills aligned with Must/Should requirements. Requires job-analysis to have run first for that company.
disable-model-invocation: true
argument-hint: "[company] [role]"
---

# CV Adaptation

## When to use this skill
Invoke with `/cv-adaptation [company] [role]` after `/job-analysis` has generated `outputs/ready/{company}/analysis.json`.
Do not run if `recommendation: skip`.

## Required inputs
- `outputs/ready/{company}/analysis.json` — job analysis result
- `assets/cv/cv_base_en.docx` — candidate's base English CV template
- `assets/cv/cv_base_es.docx` — candidate's base Spanish CV template (if applicable)

> **Template naming convention**: Name your base CV files exactly `cv_base_en.docx` (English) and `cv_base_es.docx` (Spanish) in `assets/cv/`. The scripts use these filenames.

## Execution sequence

### Step 0 — Load knowledge base
> **If this skill is invoked from inside `apply` or `apply-all`**: knowledge base is already loaded in session context — skip this step entirely.

Before any other action, read these files in order:

1. `profile.json` — master candidate record (skills, experience, projects, preferences, learning_in_progress). It is the only source of truth about what can be asserted.
2. `assets/knowledge_base/project_depth.md` — complete technical description of each project (validated metrics, exact architectures, correct framing). Use this, DO NOT invent details.
3. `assets/knowledge_base/self_framing.md` — how the candidate describes themselves; what framing is honest and what inflates the profile.
4. `assets/knowledge_base/writing_voice.md` — voice patterns, tone, vocabulary, and bullet structure. So the adapted CV sounds like the candidate and not generic AI.

If any knowledge base file doesn't exist, notify the user and continue with profile.json as minimum.

### Step 1 — Verify preconditions
Read `outputs/ready/{company}/analysis.json`.
If `recommendation == "skip"`, warn and stop.
If `fit_score < 30`, warn before continuing and ask for confirmation.

### Step 2 — Read the base CV
Read the CV content from `assets/cv/`.
Identify: experiences, projects, education, candidate's current skills.

### Step 3 — Map alignment
Cross-reference CV base skills with `skills.must` and `skills.should` from `analysis.json`:
- Experiences and projects most relevant to the role → prioritize
- Candidate skills that cover Must gaps → highlight
- Important gaps → honestly reformulate existing experiences (do not fabricate)

### Step 4 — Generate adapted CV

**BEFORE writing the JSON, if `language == "es"`**:
   - Re-read the entire "## ⚠ SPANISH MODE" section of this document to internalize Spanish generation rules. The adapted CV must strictly comply with these rules.
   - All bullets must be in Spanish from the first generation
   - Verify each bullet uses first-person preterite verbs

Build a JSON with the reordered and adapted CV:

```json
{
  "company": "string",
  "role": "string",
  "date_generated": "YYYY-MM-DD",
  "cv_version": "string",
  "language": "en | es",
  "summary": "adapted professional summary (mentions at least 2 Must skills)",
  "skills_highlighted": ["skill1", "skill2"],
  "experience": [
    {
      "title": "string",
      "company": "string",
      "period": "string",
      "description": "string (company tagline, optional)",
      "bullets": ["relevant achievement with metrics if they exist"]
    }
  ],
  "projects": [],
  "education": []
}
```

Save to `outputs/ready/{company}/cv_{company}_{role}.json`.

### Step 5 — Generate .docx

```bash
python .claude/skills/cv-adaptation/scripts/generate_cv_docx.py \
  outputs/ready/{company}/cv_{company}_{role}.json \
  outputs/ready/{company}/
```

### Step 5b — Validate language (ONLY language=es)

> **Skip if `language != "es"`** — this step applies exclusively to Spanish CVs.

Before generating the .docx, run the validator on the saved JSON:

```bash
python .claude/skills/cv-adaptation/scripts/validate_cv_es.py outputs/ready/{company}/{cv_filename}.json
```

The validator detects and auto-corrects:
- **Missing tildes and ñ** (`produccion`→`producción`, `anos`→`años`, etc.)
- **Preterite verbs without accent** (`implemente`→`implementé`, `construi`→`construí`, etc.)
- **Third person verbs** (`desarrolló`→`desarrollé`)
- **Em dashes** (`—`→`,`)
- **English job titles** → canonical Spanish translation

Actions per output:
- `N correction(s) applied`: corrections are already in the JSON. Review the report and continue.
- `⚠ SYSTEMIC TILDE FAILURE`: the model generated the JSON without diacritics — systemic failure. Corrections were applied automatically but it's a signal to re-read the Spanish Mode section.
- `⚠ ENGLISH DETECTED`: JSON has English content — regenerate in Spanish from scratch (the validator doesn't translate).
- `Without detected issues`: continue directly to Step 6.

### Step 6 — Log
Record in `logs/cv_adaptation.log` with date, company, role, and fit_score.

## Validation rules

### No fabrication (CRITICAL)
- The adapted CV MUST NOT contain false or invented information. It is allowed to reformulate, reorder, emphasize, or de-emphasize existing content; it is NOT allowed to add responsibilities, achievements, or experiences not documented in the base CV or in the analysis JSON. The presence of a skill in the `skills` array does not authorize creating employment bullets for experiences that didn't happen.
- If there is a real gap in a Must skill: document it honestly in `adaptations_made` and optionally mention the candidate is developing that skill — but never simulate past experience that doesn't exist.

### Professional Summary rule
- Rewrite the `summary` for each application, adjusting framing to the role context. Maximum 4 sentences.
- Never copy the base CV summary verbatim; always rewrite with focus on the role context.
- Must mention ≥2 Must skills from the posting.
- Refer to `self_framing.md` for how the candidate positions themselves.

### No-bridging-language
- Never explain to the recruiter why the experience is relevant to the role — show the experience and let the recruiter make the connection.
- Eliminate any phrase containing: "directly applicable to", "aligned with", "which maps directly to", "equivalent to", "mirrors", "translates directly to", "analogous to [role context]", "relevant to this position", "directly relevant".
- BAD: "Built a LightGBM model — directly applicable to the credit risk scoring this role requires"
- GOOD: "Built a Lapse Prediction model (LightGBM) deployed in weekly batch scoring on cloud, scoring 1M+ records per run"

### Output language

The adapted CV language must match the original posting language. Read the `language` field from `analysis.json`: `"en"` → English, `"es"` → Spanish. All JSON content must be entirely in that language without mixing.

### Em dash restriction (GOLDEN RULE)
- **PROHIBITED em dash "—" in bullets, summary, and any CV body text.** No exceptions.
- Also prohibited: ` - ` (space-hyphen-space) as an intra-sentence clause separator
- Alternatives: rewrite as two separate sentences, use `, ` or `;`, or restructure the phrase
- Hyphen in compound words is allowed (no spaces): `out-of-time`, `K-means`, `end-to-end`
- En-dash in numeric ranges and periods is allowed: `2022–Present`, `Jan 2020 – Feb 2025`

### Prohibited phrases and words
Replace with specific, concrete language:
- ❌ "actionable insights" → describe what specific insight and what action it drove
- ❌ "data-driven decisions" → describe what decision and with what data
- ❌ "leveraging" → use "using", "applying", or reformulate directly
- ❌ "seamless" → eliminate or describe specifically how it works
- ❌ "robust pipeline" → describe what the pipeline does and its scale
- ❌ "production-quality" → if it's production, describe it: frequency, scale, stack
- ❌ "executive-ready" → eliminate

### Bullet variety
- NOT all bullets need an impact/result clause. Vary the structure:
  - ~60% of bullets with impact or quantifiable result
  - ~40% descriptive of method, scope, or scale
- Vary the opening structure: avoid all bullets starting with the same verbal pattern (e.g., don't start all with "Built")

### Professional Summary — mandatory first person
The adapted `summary` MUST be entirely in first person. All conjugated verbs must be first person: "I have worked", "I apply", "I work fluently".
- ❌ Prohibited: "Has worked across risk-adjacent domains" / "Applies a rigorous MLOps discipline"
- ✅ Correct: "I have worked across risk-adjacent domains" / "I apply a rigorous MLOps discipline"
- The nominal opening "Data Scientist with 5+ years of experience building..." is acceptable without a subject. Conjugated verbs that follow MUST be first person.

### Skills without experience backing (critical extension)
Skills present in `profile.skills[]` that have NO documented achievement in `profile.experience[]` or `profile.projects[]` MUST NOT appear as employment bullets. If the skill is relevant to the role, document it honestly in `adaptations_made` as a gap and use `learning_in_progress` framing.

### Do not inflate seniority in summary
Never change the candidate's seniority level in the Professional Summary unless the CV header title is also updated consistently. Frame experience as senior-level without changing the title label.

### Exact academic degree name
Always use the exact name documented in `profile.education[]`. Never abbreviate or paraphrase.

### Do not inflate quantitative data
Never round up or extrapolate quantitative claims. If the source says "5+ clients", the output must say exactly "5+ clients".

### Bullet budget by experience (2-page limit)
Set bullet limits per position to keep the CV to 2 pages. Configure these limits based on your own experience priorities:
- Most recent/relevant role: maximum 5 bullets (keep full detail)
- Second most relevant: maximum 3 bullets
- Third: maximum 2 bullets
- Earlier positions / minor roles: 0–1 bullets (header only if very old/irrelevant)

> **Customize**: Update this table to reflect your specific experience. Positions in `profile.experience[]` that predate your data/ML career may need 0 bullets.

If you must cut, prioritize older experiences.
Do not repeat concepts between bullets of the same company.
Available bullets in the base CV are the selection pool — do not invent new ones.

### Personal Projects section — critical rule

The `projects` section of the JSON has one purpose: list **personal/side projects** of the candidate. Not work projects.

**PROHIBITED in `projects`**: any project developed in a professional context (work for a company or client). Those projects are already covered as bullets in the `experience` section. Duplicating them in `projects` is an error.

**If the candidate has a personal agentic/automation system** (such as this job search pipeline itself), it can be included in projects using **completely domain-agnostic framing** — NEVER mention the specific domain it automates. Describe the technical stack and capabilities generically.

Example framing for a personal agentic project:

- **Roles of high relevance** (AI Engineer, ML Engineer, Applied AI, agentic/LLM roles): use `bullets` format with 3 detailed technical bullets.
- **Standard roles** (Data Scientist, Analytics Engineer, consulting): use `description` format with 1-2 concise sentences.

**EN — detailed bullets** (high relevance):
```json
{
  "name": "Agentic System",
  "year": "2025–2026",
  "context": "Personal Project",
  "bullets": [
    "Designed and built a multi-agent orchestration system using Claude Code and the Anthropic Python SDK; an Orchestrator coordinates specialized agents (Parser, Scorer, Generator, Critic/QA), each with defined tool schemas, typed inputs, and structured outputs.",
    "Implemented a semantic relevance scoring engine (Must/Should/Nice weighted algorithm), JSON-based document templating with dynamic field injection, and HITL approval gates before each pipeline stage.",
    "Integrated Google Sheets API for end-to-end tracking and a Chart.js analytics dashboard for monitoring pipeline outputs; batch mode processes a full input queue autonomously with error recovery."
  ]
}
```

**EN — compact description** (standard roles):
```json
{
  "name": "Agentic System",
  "year": "2025–2026",
  "context": "Personal Project",
  "description": "Built a multi-agent pipeline using Claude Code and the Anthropic Python SDK to automate a complex workflow end-to-end: parsing input sources, scoring relevance across weighted criteria, generating and adapting structured content, and producing final documents, with HITL review gates, Google Sheets tracking, and a Chart.js dashboard for monitoring pipeline outputs."
}
```

---

## ⚠ SPANISH MODE — Activate when `language == "es"`

> This section is a complete protocol. Read it entirely before generating any content in Spanish.
> The `validate_cv_es.py` script (Step 5b) auto-detects and corrects: missing tildes, missing ñ, preterite verbs without accent, and third person instead of first. If it detects ≥4 tilde errors in the same field, it reports SYSTEMIC TILDE FAILURE.
> Even so: **this is not an excuse to generate them**. Claude must produce content with correct tildes from the first pass.

### Rule 1 — Mandatory first person

All action verbs in bullets and summary MUST be conjugated in first person singular simple preterite:

| Incorrect (3rd person) | Correct (1st person) |
|---|---|
| gestionó | gestioné |
| diseñó | diseñé |
| implementó | implementé |
| construyó | **construí** (irregular) |
| lideró | lideré |
| desarrolló | desarrollé |
| dirigió | dirigí |
| realizó | realicé |
| desplegó | desplegué |
| optimizó | optimicé |
| automatizó | automaticé |

- ❌ Gerunds as bullet main verb: "gestionando pipelines" → use "gestioné pipelines"
- ❌ Third person present: "trabaja con Python" → "trabajo con Python"

### Rule 2 — Job title translation

The `title` field of each experience MUST be in Spanish. Use canonical translations appropriate to the candidate's actual titles (documented in `profile.experience[]`).

**DO NOT translate**: company names, technical terms (Python, SQL, LightGBM, GCP, BigQuery, Airflow, Vertex AI, Cloud Composer), certifications, frameworks.

### Rule 3 — Language consistency in all JSON fields

When `language == "es"`, the following JSON fields MUST be in Spanish:
- `summary` — entirely in Spanish
- `bullets` (and `adapted_bullets`) of each experience — entirely in Spanish
- `title` of each experience entry — per translation in Rule 2
- `projects[].description` — entirely in Spanish

Section headers in the .docx are translated automatically by `generate_cv_docx.py` when `language == "es"` — not necessary to write them in the JSON.

### Rule 4 — No em dashes in Spanish

Same rule as in English: `—` prohibited in bullets and summary.

### Rule 5 — First person in Professional Summary

The JSON `summary` field MUST be entirely in first person. Conjugated verbs use first person of present or preterite.

---

## Error handling

| Error | Action |
|---|---|
| `analysis.json` doesn't exist | Run `/job-analysis [company] [role]` first |
| Base CV not found in `assets/cv/` | Stop and request the file |
| `fit_score < 30` | Warn, ask confirmation before continuing |
| Unmitigable Must gaps | Document honestly in JSON, do not fabricate |

## Edge cases
- Roles with multiple required stacks: prioritize Must over Should in bullets
- Second application to same company: generate completely new version with suffix `_v2`
- Very technical role: balance between narrative and demonstration of technical competence with metrics

## Note on scripting
This skill has no Python script for adaptation — Claude performs the adaptation directly
by reading inputs and writing the JSON output. This allows strategic reasoning
about how to present experiences, which is not deterministically automatable.
