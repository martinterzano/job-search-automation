---
name: apply-all
description: Scans jobs_inbox/ and runs the full /apply pipeline for each unprocessed posting. Ideal for processing multiple postings at once without running /apply individually.
disable-model-invocation: true
---

# Apply-All — Batch Pipeline

## When to use this skill
Invoke with `/apply-all` after adding one or more `.txt` files to `jobs_inbox/`.
The skill automatically detects which ones haven't been processed and processes them in sequence.

---

## Step 0 — Load knowledge base (once for the entire pipeline)

Before processing any posting, read these files in order. They are loaded **once** for the entire session; sub-skills (cv-adaptation, cover-letter, critic) will skip their own Step 0 when they detect KB is already in context.

1. `profile.json`
2. `assets/knowledge_base/project_depth.md`
3. `assets/knowledge_base/self_framing.md`
4. `assets/knowledge_base/writing_voice.md`

---

## Step 1 — Scan the inbox

List all files in `jobs_inbox/*.txt`.

For each file:
- Calculate the `{stem}`: filename without extension and without any "Logo of " prefix if present
- Verify if the stem directory exists in any of the three states:
  - `outputs/ready/{stem}/analysis.json`
  - `outputs/applied/{stem}/analysis.json`
  - `outputs/discarded/{stem}/analysis.json`
- Classify: **pending** if it doesn't exist in any, **already processed** if it exists in any

This mechanism correctly supports multiple roles per company
(e.g., `Google_Senior_Data_Scientist.txt` and `Google_ML_Engineer.txt` are independent jobs).

For each pending file, read its content and look for phrases indicating the application should be made **by email** (rather than a job portal). Patterns to detect (case-insensitive):

- `please email` / `send.*email` / `apply.*email` / `email.*apply`
- `email your CV` / `email your resume` / `send your CV to` / `send your application to`
- `applications to [email@]` / `to apply.*contact` / `contact us at [email@]`
- Any email address in the context of application instructions
- `apply by sending` / `please send.*to` / `submit.*to [email@]`

Mark files where any of these patterns is detected with the flag `email_only: true`.

Show the user the inbox status:

```
Inbox scanned: {N} files found
  ✓ Already processed (skip): {list}
  ⚠ Duplicates (same posting already processed — skip): {list}   ← completed in Step 1b
  → Actual pending (to process): {n} files
    1. {filename_1}  ✉ APPLY BY EMAIL — do not use portal ({email_detected})
    2. {filename_2}
    ...
```

The `✉ APPLY BY EMAIL` annotation appears only for postings where an email application instruction was detected. Show the detected email in parentheses if visible in the text.

If no pending files: inform the user and stop.

---

## Step 1b — Duplicate detection

For each file classified as **pending**, verify if it's the same posting as one already processed:

1. Extract `{company_name}` from the stem by removing any date/numbering suffix if present
2. Search in `jobs_inbox/*.txt` for other files that:
   - Are not the current file
   - Whose stem contains the same `{company_name}`
   - Are **already processed** (have a directory in `outputs/ready/`, `outputs/applied/`, or `outputs/discarded/`)
3. If at least one candidate is found:
   - Read the pending file content with Read
   - Read the already processed file content with Read
   - Compare: same company, same role, same essential requirements?
   - If they're the same posting → reclassify as **DUPLICATE**
   - If there are substantial differences (different role, different requirements) → not a duplicate, keep as pending

4. Reclassify the inbox summary with detected duplicates.

Duplicates are NOT processed. If all pending files turned out to be duplicates: inform the user and stop.

---

## Step 1.5 — Pre-screening

For each actual pending file (real, not duplicate), read its content and classify the 5 pre-screening dimensions. This step happens **before** running any script.

### Dimensions to classify

**1. `company_type`** — type of company
- `product_company` — own product, DS is a core internal function
- `consultora_ds` — does DS projects for clients (DS consulting)
- `staff_augmentation` — places profiles in client projects (body shop)
- `startup_early` — pre-Series A or without a clear product in production
- `corporate` — large company with an established internal DS team
- `unknown` — cannot be determined from the text

**2. `role_core`** — main deliverable of the role
- `ml_modeling` — predictive models, classification, clustering as central output
- `analytics_bi` — dashboards, reports, KPIs as central output without substantial ML
- `product_ds` — A/B testing, experimentation, product metrics as the axis
- `mlops_engineering` — ML infrastructure, deployment, pipelines as the axis
- `research` — research, papers, novel architectures
- `mixed` — ML modeling + another significant component

**3. `seniority_required`** — explicitly required level
- `junior` (0–2 years required)
- `mid` (2–4 years)
- `senior` (4+ years)
- `lead` (explicit team leadership)

**4. `stack_gaps`** — role must-haves that the candidate doesn't have (leave empty if none)
- `pytorch_dl_must` — PyTorch / deep learning as a non-negotiable requirement
- `ab_testing_core` — A/B testing / experimentation as the role axis (not just "nice to have")
- `databricks_must` — Databricks as the main stack without a cloud alternative
- `computer_vision_must` — computer vision as a must
- `spark_scala_must` — Spark / Scala / Java as the main stack

> **Customize**: Review these stack_gaps against `profile.json` `learning_in_progress` and skills. Add or remove flags based on your actual gaps.

**5. `domain`** — industry / company domain
- High affinity: depends on candidate's documented industry experience (see `profile.json`)
- Neutral: industries where the candidate has no documented experience but no strong barriers
- Low affinity: industries with cultural or technical barriers for the candidate

---

### Pre-screening logic

**🔴 Auto-SKIP** — does not enter the pipeline:
- `company_type = staff_augmentation`
- `role_core = analytics_bi` (without substantial ML as deliverable)
- `seniority_required = junior`
- Salary below `profile.preferences.min_salary` explicit in the text (read from profile.json)
- `stack_gaps` contains `computer_vision_must` or `spark_scala_must`
- Role is "Data Analyst" without explicit ML modeling in responsibilities
- `sponsorship_required: true` in profile.json AND posting says "no sponsorship" / "must be authorized to work"

**⚠️ FLAG — show for user decision:**
- `company_type = consultora_ds` or `startup_early`
- `role_core = product_ds` or `mlops_engineering`
- `stack_gaps` contains `pytorch_dl_must`, `ab_testing_core`, or `databricks_must`
- Low affinity domain
- Anonymous/confidential company without clear domain signals
- `sponsorship_required: true` in profile.json AND posting is silent on sponsorship

**✅ PROCESS** — enters pipeline without question:
- `company_type = product_company` or `corporate`
- `role_core = ml_modeling` or `mixed` with dominant ML
- `seniority_required = senior` or `mid`
- `stack_gaps = []`
- High affinity domain

---

### Pre-screening table

Show the table for **all** actual pending files before processing anything:

```
PRE-SCREENING — {n} pending
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Company              Role                  Type          Core      Domain       Gaps            Rec
──────────────────────────────────────────────────────────────────────────────────────────────────────
1  ✅ Company A          Data Scientist        Corporate     ML        Fintech      —               PROCESS
2  ⚠️  Company B          Data Scientist        Startup       ML        SaaS         —               REVIEW · startup early
3  🔴 Company C          Data Analyst          Staff-aug     No-ML     Various      —               SKIP · body shop · no ML
4  ⚠️  Company D          Senior DS             Consultancy   ML        Gaming       pytorch_dl      REVIEW · neutral domain · DL gap
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 1 PROCESS · ⚠️ 2 REVIEW · 🔴 1 SKIP
```

**Ask:** "Confirm? Any changes before processing?"

Wait for response before continuing. The user can:
- Confirm everything → respect the recommendations
- Change specific decisions ("process #3 anyway", "also skip #2")

---

### Post-confirmation processing

**Jobs confirmed as SKIP (automatic or user-changed):**

1. Create minimal `outputs/discarded/{company}_{role}/analysis.json`:
```json
{
  "company": "...",
  "role": "...",
  "date_processed": "YYYY-MM-DD",
  "fit_score": 0,
  "recommendation": "skip",
  "interpretation": "Discarded in pre-screening: {reason}.",
  "company_summary": "...",
  "role_summary": "..."
}
```
2. Register in tracker:
```bash
python .claude/skills/apply/scripts/update_tracker.py outputs/discarded/{company}_{role}/analysis.json
```
3. Do not run job-analysis, cv-adaptation, cover-letter, or critic.

**REVIEW jobs approved by user and PROCESS jobs:** proceed to Step 2.

---

## Step 2 — Process each approved pending

For each file approved in pre-screening (PROCESS or confirmed REVIEW), run the full `/apply` pipeline using the `.txt` content as the raw posting text.
Outputs follow exactly the same schema as `/apply`: `outputs/ready/{company}_{role}/`.

**Name conflict resolution**: if when extracting `{company}` and `{role}` from the posting content the directory `outputs/ready/{company}_{role}/` already exists (from another job processed in the same batch), add a numeric suffix: `outputs/ready/{company}_{role}_2/`, `_3/`, etc.

Show progress before each pipeline:

```
[{i}/{total}] Processing: {filename}
──────────────────────────────────────────────────
```

Execute all `/apply` steps in order:

**2a — Get posting text**
Read the content of `jobs_inbox/{filename}` with Read.
Use that content as the raw posting text (not as a URL).

**2b — Get company context**
From the company name extracted from the posting content, attempt **a single WebFetch**:
- `https://{domain}/about`

If it fails (timeout, 404, blocked): use only the company information that appears inside the posting. Do not retry with other paths.

Save to `.tmp/{company}_context.txt`.

**2c — job-analysis**

Read and follow **in full** the instructions in `.claude/skills/job-analysis/SKILL.md`.

The input is the text file saved in `jobs_inbox/{filename}` (or `.tmp/{stem}_clean.txt` if the posting came from LinkedIn and was cleaned). The consolidated output must go in `outputs/ready/{company}_{role}/analysis.json`.

Apply all rules, validations, qualitative adjustments, and reasoning logic defined in that SKILL.md — including candidate context enrichment (Step 3.5), qualitative scoring rules (Step 4), and the complete output schema.

**2d — cv-adaptation**

Read and follow **in full** the instructions in `.claude/skills/cv-adaptation/SKILL.md`.

The input is `outputs/ready/{company}_{role}/analysis.json` generated in 2c.
Outputs must go in `outputs/ready/{company}_{role}/cv_{company}_{role}.json` and `outputs/ready/{company}_{role}/cv_{company}_{role}.docx`.

Apply all rules from that SKILL.md: knowledge base loading (Step 0), alignment mapping, no-fabrication rules, dash restriction, bullet budget, prohibited phrases, and all additional rules defined there.

**2d bis — Generate CV PDF**

```bash
python .claude/skills/cv-adaptation/scripts/generate_cv_pdf.py \
    outputs/ready/{company}_{role}/cv_{company}_{role}.json \
    outputs/ready/{company}_{role}/
```

Output: `outputs/ready/{company}_{role}/CV_{company}_{CandidateLastName}.pdf`

**2e — cover-letter**

Read and follow **in full** the instructions in `.claude/skills/cover-letter/SKILL.md`.

Inputs are `outputs/ready/{company}_{role}/analysis.json`, `outputs/ready/{company}_{role}/cv_{company}_{role}.json`, and `.tmp/{company}_context.txt`.
Output must go in `outputs/ready/{company}_{role}/cover_letter_{company}_{role}.docx`.

Apply all rules from that SKILL.md: knowledge base loading (Step 0), content and style rules, opening/closing restrictions, prohibited phrases, word count limit, and all additional restrictions defined there.

**2f — Critic Agent (AUTO mode)**

Read and follow **in full** the instructions in `.claude/skills/critic/SKILL.md`, operating in **AUTO MODE**.

Without pausing the flow or asking for confirmation. Apply only corrections defined as auto-applicable in that SKILL.md.

Always save the report (even if PASS):
```
outputs/ready/{company}_{role}/critic_report_{company}_{role}.json
```

**2g — Register in Google Sheets tracker + regenerate dashboard**
```bash
# 2g-1: Update Google Sheets tracker (append row with color)
python .claude/skills/apply/scripts/update_tracker.py outputs/ready/{company}_{role}/analysis.json

# 2g-2: Regenerate HTML dashboard
python .claude/skills/apply/scripts/generate_dashboard.py
```

**Handling `recommendation: skip` within the batch**
If a pipeline's fit score results in `recommendation: skip`: DO NOT stop the batch.
- Skip steps 2d (cv-adaptation), 2d bis (PDF), 2e (cover-letter), and 2f (critic).
- Still run step 2g (update_tracker) — SKIP jobs **must** be registered in the tracker.
- Record as SKIP in the final summary and continue with the next file.

**Handling `recommendation: conditional` within the batch**
Run the full pipeline (2d, 2e, 2f, 2g) same as for `apply`.

---

## Step 3 — Final batch summary

When all pipelines are finished, show:

```
══════════════════════════════════════
APPLY-ALL COMPLETE — {n} processed
══════════════════════════════════════
  ✓ {company} / {role}  → Fit: {score} ({RECOMMENDATION})
  ✓ {company} / {role}  → Fit: {score} ({RECOMMENDATION})
  ✗ {company} / {role}  → Fit: {score} (SKIP — omitted)
  🔴 {company} / {role}  → SKIP pre-screening ({reason})
  ⊘ {company} / {role}  → DUPLICATE (skipped — same posting already processed)
  ...

Tracker updated: Google Sheets · Dashboard regenerated: outputs/dashboard.html

[Include only if critic updated any SKILL.md during this batch:]
──────────────────────────────────────
SKILL.MDs UPDATED IN THIS BATCH:
  → {skill_md_path}: {brief_description} [{company} / {role}]
──────────────────────────────────────
══════════════════════════════════════
```

---

## Error handling

| Error | Action |
|---|---|
| `jobs_inbox/` empty or no `.txt` | Inform and stop |
| All files already processed | Inform and stop |
| Company or role not inferable from posting content | Ask user before processing that file |
| `profile.json` not found | Stop the entire batch and request it |
| Error in an individual pipeline | Log the error, continue with the next file |
| Google Sheets without credentials / connection error | Inform user — do not interrupt the batch. Check `assets/google/credentials.json` and `GOOGLE_SHEETS_SPREADSHEET_ID` in `.env` |
| Dashboard HTML fails to generate | Inform user — do not interrupt the batch. Tracker may be OK even if dashboard fails |
