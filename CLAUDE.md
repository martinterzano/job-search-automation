# CLAUDE.md — Job Search Automation Template

## What this project is
An agentic pipeline for automating Data Science job search, built with Claude Code Skills.
It analyzes job postings, calculates fit scores, adapts your CV, and generates personalized cover letters.

## Getting started
If you haven't set up your personal files yet, start here:
```
/setup all
```
This will guide you through creating `profile.json` and all knowledge base files interactively.

## Available skills (invoke with `/`)

| Skill | Command | When to use |
|---|---|---|
| setup | `/setup [all\|profile\|voice\|framing\|depth\|validate]` | **First time setup** — creates your personal config files |
| job-analysis | `/job-analysis [company] [role]` | When you receive a new job posting |
| cv-adaptation | `/cv-adaptation [company] [role]` | After job-analysis |
| cover-letter | `/cover-letter [company]` | After cv-adaptation |
| critic | `/critic [company] [role]` | After cover-letter — HITL review of CV and CL |
| apply | `/apply [url\|text]` | Full end-to-end pipeline for a single posting |
| apply-all | `/apply-all` | Batch: processes all .txt files in jobs_inbox/ |
| dashboard | `/dashboard` | Regenerates outputs/dashboard.html from Google Sheet |

Manual order: `job-analysis` → `cv-adaptation` → `cover-letter` → `critic`
`apply` and `apply-all` run the full pipeline (including critic in AUTO mode).

## Key file structure

```
.claude/skills/          → Skills with their encapsulated scripts
assets/cv/               → Your base CV templates (cv_base_en.docx, cv_base_es.docx)
assets/cover_letters_examples/  → Your past cover letters (style reference)
assets/knowledge_base/   → Synthesized knowledge base — read BEFORE generating any output
  writing_voice.md       →   Your voice, tone, and vocabulary
  self_framing.md        →   How you describe yourself honestly (gaps and strengths)
  project_depth.md       →   Complete technical description of each project
profile.json             → Master candidate record — single source of truth
jobs_inbox/              → Raw unprocessed job postings (.txt files)
jobs_parsed/             → Parsed postings as JSON
outputs/{company}/       → Results per company (analysis, cv, cover letter)
outputs/dashboard.html   → Auto-generated HTML dashboard
logs/                    → Execution logs
assets/google/           → Google OAuth credentials (credentials.json, token.json — don't version)
  SETUP.md               →   Initial Google Cloud setup instructions
.env                     → ANTHROPIC_API_KEY + GOOGLE_SHEETS_SPREADSHEET_ID (don't version)
```

## Knowledge base — reading hierarchy in skills

All skills that generate content (cv-adaptation, cover-letter, critic) read these files BEFORE reasoning:

1. `profile.json` — source of truth (what can be asserted)
2. `assets/knowledge_base/project_depth.md` — precise technical context per project
3. `assets/knowledge_base/self_framing.md` — honest framing of gaps and strengths
4. `assets/knowledge_base/writing_voice.md` — voice, tone, and writing style

## Operational rules

- **No fabrication**: The adapted CV must not contain false data
- **No LinkedIn scraping**: use only permitted sources
- **JSON outputs**: full traceability per company/role
- **Versioned per company**: each output is independent, never mix between companies
- **Fit score < 30**: warn before continuing with cv-adaptation
- **Recommendation: skip**: do not continue the pipeline for that posting

## Required environment variables
`ANTHROPIC_API_KEY` — required for `generate_cover_letter.py`
`GOOGLE_SHEETS_SPREADSHEET_ID` — tracker in Google Drive (obtained on first run of `update_tracker.py`)

## Candidate profile
See `profile.json` for current skills, experience, and role preferences.
See `assets/cv/` for the complete base CV.
See `assets/knowledge_base/` for synthesized knowledge base files.
