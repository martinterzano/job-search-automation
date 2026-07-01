---
name: setup
description: Interactive onboarding — guides the user step by step to create profile.json and knowledge_base files from scratch. Run this before using any other skill.
disable-model-invocation: true
argument-hint: "[profile|voice|framing|depth|all|validate]"
prerequisites: "None — this is the starting point"
---

# Setup — Interactive Onboarding

## When to use this skill
Invoke with `/setup [subcommand]` to create the personal configuration files required before the pipeline can run.

Available subcommands:
```
/setup profile   → Create profile.json interactively
/setup voice     → Synthesize writing_voice.md from your examples
/setup framing   → Create self_framing.md via Q&A
/setup depth     → Create project_depth.md project by project
/setup all       → Full flow in order (profile → voice → framing → depth)
/setup validate  → Verify all files exist and have no placeholders
```

**Recommended starting point**: `/setup all` for a new installation.

---

## /setup validate

Run first to check what's missing:

```bash
python .claude/skills/setup/scripts/validate_setup.py
```

The script checks:
1. `profile.json` — exists and has no placeholder values (`YOUR_FULL_NAME`, `YOUR_EMAIL`, etc.)
2. `assets/knowledge_base/writing_voice.md` — exists and has content beyond the template instructions
3. `assets/knowledge_base/self_framing.md` — exists and has content beyond the template instructions
4. `assets/knowledge_base/project_depth.md` — exists and has content beyond the template instructions
5. `assets/cv/cv_base_en.docx` — exists (base English CV template)
6. `.env` — exists (or `.env.example` filled)

Output: checklist showing COMPLETE / MISSING / PLACEHOLDER for each file.

If everything is complete: inform the user the project is ready to use and stop.

---

## /setup profile

### Purpose
Create `profile.json` from scratch through structured questions.

### Step 1 — Check if profile.json already exists
Read `profile.json`. If it exists and has real content (not placeholders): ask "profile.json already exists. Overwrite or update a specific section?" and wait.

### Step 2 — Collect personal information
Ask the user the following, in a conversational tone (one question at a time or grouped logically):

**Basic info:**
- Full name
- Email
- Phone (optional)
- LinkedIn URL (optional)
- City and country of residence
- Nationalities / work authorization (important for sponsorship if applicable)

**Career:**
- Years of experience in data/ML (approximately)
- One-sentence professional summary (how do you describe yourself?)
- Target roles (e.g., Senior Data Scientist, ML Engineer, AI Engineer)
- Target industries (e.g., fintech, healthtech, SaaS — or "open to all")
- Preferred modality (remote / hybrid / on-site)
- Minimum salary and currency (e.g., $150K USD, 60K EUR)
- Do you require visa sponsorship? (yes/no)

**Skills:**
Walk through each category:
- Programming languages (Python, SQL, R, etc.)
- ML frameworks (scikit-learn, LightGBM, XGBoost, PyTorch, etc.)
- Cloud platforms (GCP, AWS, Azure)
- MLOps tools (Airflow, Vertex AI, MLflow, etc.)
- Data tools (BigQuery, Spark, dbt, etc.)
- LLM / Agentic tools (Anthropic API, LangChain, Claude Code, etc.)
- Currently learning (skills in progress — mark as `learning_in_progress`)

**Work experience:**
For each position (most recent first):
- Job title
- Company name
- Start and end dates
- 3-5 key achievements or responsibilities (brief bullets, full detail will go in knowledge_base)

**Projects:**
For each significant project:
- Project name
- Year
- Brief description (1-2 sentences)
- Context: personal project, professional, academic?

**Education:**
- Degree name (use exact name, not abbreviations)
- Institution
- Year graduated / in progress

**Languages:**
- Native language
- Other languages and level

### Step 3 — Build and save profile.json
Once all information is collected, build the complete JSON in session:

```bash
python .claude/skills/setup/scripts/save_profile.py profile_draft.json
```

where `profile_draft.json` is a temp file with the collected data, or pass via stdin.

Alternatively, write `profile.json` directly with the Write tool after confirming with the user.

After saving, show a summary:
```
profile.json created ✓
  Name: [name]
  Experience: [years]+ years
  Skills: [N] documented
  Experience entries: [N]
  Projects: [N]
  Run /setup validate to check completeness.
```

---

## /setup voice

### Purpose
Create `assets/knowledge_base/writing_voice.md` by analyzing real samples of the candidate's writing.

### Step 1 — Request writing samples
Ask the user to provide:
- 2-3 cover letters they've written in the past (paste the full text)
- Optionally: 1-2 technical articles, LinkedIn posts, or blog posts they've written
- Optionally: responses to interview questions they've prepared

**Important**: the more authentic samples, the better the voice synthesis. Even one good cover letter is enough to start.

### Step 2 — Analyze and synthesize
Read all provided samples carefully. Identify:

1. **Tone profile**: formal/informal balance, first-person or distanced, confident or humble
2. **Sentence patterns**: typical length, complexity, rhythm. Do they use lists? Long paragraphs? Short punchy sentences?
3. **Opening strategies**: how do they start letters? Narrative hook? Direct intro? Methodological framing?
4. **Closing strategies**: how do they close? Call to action? Future direction? Implicit invitation?
5. **Vocabulary**: recurring words, technical terms they prefer, metaphors or analogies they use
6. **What they avoid**: clichés they naturally don't use, registers that don't feel like them
7. **Company connection patterns**: how do they express genuine interest in companies? What details do they highlight?
8. **Metric usage**: do they cite numbers? What kind? What do they avoid?

### Step 3 — Write and save writing_voice.md
Generate the synthesized voice document and save to `assets/knowledge_base/writing_voice.md`.

Structure:
```markdown
# Writing Voice — [CANDIDATE_NAME]
## Tone Profile
## Sentence Patterns
## Opening Strategies (4 documented patterns)
## Closing Strategies
## Vocabulary Patterns
  - Technical language
  - Narrative language
  - What to avoid
## Company Connection Patterns
## Metric and Achievement Framing
## Bilingual Notes (if applicable)
```

Confirm with the user before saving.

---

## /setup framing

### Purpose
Create `assets/knowledge_base/self_framing.md` through an honest Q&A about the candidate's strengths, gaps, and how to describe themselves.

### Questions to ask (conversational, one at a time)

**Experience and level:**
- How many years of experience do you have specifically in ML / data science? (not general data work)
- How do you describe your SQL level? (basic / intermediate / advanced / expert)
- What's the most complex end-to-end ML project you've shipped to production?

**Stack honesty:**
- Which tools in your profile are you genuinely proficient with vs. which have you only used occasionally?
- Is there anything in your skills list that you'd feel uncomfortable being asked about in a technical interview? (mark as `learning_in_progress`)
- What are you actively learning right now?

**Gap acknowledgment:**
- Are there any common job requirements you typically don't meet? (e.g., A/B testing, NLP, specific cloud platforms)
- How do you usually describe these gaps to recruiters? What framing feels honest?

**Domain and context:**
- Which industries have you worked in directly? (only count documented experience)
- Have you worked in regulated environments (finance, healthcare, insurance)?
- Have you deployed models to production? What was the scale?

**Years of experience claim:**
- What's the right way to say your years of experience? (e.g., "5+ years", "6 years", "8+ years")
- From what year do you count? (e.g., from first full-time data role, from first ML project, from current trajectory)

### Save self_framing.md
Generate the document capturing honest self-positioning and save to `assets/knowledge_base/self_framing.md`.

---

## /setup depth

### Purpose
Create `assets/knowledge_base/project_depth.md` with complete technical details for each significant project.

### For each project in profile.json

Ask (for each project listed in profile.json):

**Architecture:**
- What ML algorithm(s) did you use? Why that choice?
- What was the feature engineering approach?
- What was the training and validation methodology? (train/test split, OOT validation, cross-validation)

**Scale and production:**
- What was the data size? (rows, features, time span)
- Is the model in production? How often does it run? (batch daily/weekly, real-time)
- What infrastructure does it run on?

**Ownership:**
- What was your exact role? (sole owner / contributor / lead / team member)
- What percentage of the work did you do?

**Outcomes:**
- What was the measurable outcome? (outperformed baseline, reduced churn by X%, improved precision)
- What business decision does the model drive?

**Framing rules:**
- Are there any metrics that are too technical for a recruiter to understand? (e.g., Spearman, AUC, RMSE)
- What's the right way to describe the outcome without using those metrics?
- Is there anything about this project you should NOT claim (e.g., someone else's work, not yet in production)?

### Save project_depth.md
For each project, write a structured section in the document and save to `assets/knowledge_base/project_depth.md`.

---

## /setup all

Run the full onboarding flow in this order:
1. `/setup validate` — show current status
2. `/setup profile` — if profile.json is missing or incomplete
3. `/setup voice` — if writing_voice.md is missing or template-only
4. `/setup framing` — if self_framing.md is missing or template-only
5. `/setup depth` — if project_depth.md is missing or template-only
6. `/setup validate` — final check

After each subcommand completes, show progress and confirm before continuing.

---

## Scripts available
- [`scripts/validate_setup.py`](scripts/validate_setup.py) — checks all required files exist and have real content
- [`scripts/save_profile.py`](scripts/save_profile.py) — saves a profile JSON draft to `profile.json`
