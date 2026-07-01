# Job Search Automation — Claude Code Skills Template

An agentic pipeline for automating Data Science job search. Built with [Claude Code Skills](https://docs.anthropic.com/en/docs/claude-code/skills).

Drop a job posting URL, get a tailored CV and cover letter in minutes.

## What it does

1. **Parses** job postings (URL or pasted text) and classifies requirements as Must / Should / Nice-to-Have
2. **Scores** candidate fit (0–100) using a weighted algorithm with semantic aliases
3. **Pre-screens** in batch — auto-skips body shops, junior roles, off-stack positions
4. **Adapts** your CV, prioritizing the most relevant experience for each posting
5. **Generates** cover letters in your authentic voice (synthesized from your own writing)
6. **Critiques** outputs automatically — catches AI flags, fabrications, and rule violations
7. **Tracks** everything in Google Sheets and generates an HTML analytics dashboard

All outputs go to `outputs/ready/{company}_{role}/` — CV (.docx + .pdf), cover letter (.docx), and a critic report.

## Demo

```
/apply https://jobs.lever.co/company/data-scientist-123
```

Or batch-process multiple postings:
```bash
# Drop .txt files with job text in jobs_inbox/
/apply-all
```

## Prerequisites

- Python 3.9+
- [Claude Code](https://claude.ai/code) (desktop app or CLI)
- Anthropic API key ([get one here](https://console.anthropic.com/settings/api-keys))
- Microsoft Word (for PDF generation on Windows — optional)
- Google account (for Sheets tracker — optional but recommended)

## Installation

```bash
git clone https://github.com/YOUR_USERNAME/job-search-template
cd job-search-template

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Setup (first time)

Open the project folder in Claude Code and run:

```
/setup all
```

This guided flow creates:
1. `profile.json` — your master candidate record (skills, experience, projects, preferences)
2. `assets/knowledge_base/writing_voice.md` — your voice and tone synthesized from your past writing
3. `assets/knowledge_base/self_framing.md` — honest assessment of your strengths and gaps
4. `assets/knowledge_base/project_depth.md` — technical depth for each project

Then add your base CV to `assets/cv/`:
- Name it exactly `cv_base_en.docx` (English) and `cv_base_es.docx` (Spanish, optional)
- See `assets/cv/README.md` for formatting requirements

### Google Sheets setup (optional but recommended)

The tracker and dashboard require Google OAuth. One-time setup (~10 minutes):

```
See assets/google/SETUP.md for step-by-step instructions
```

After setup, the tracker auto-creates on first run of `update_tracker.py`. The Spreadsheet ID is saved to `.env` automatically.

## Usage

### Single job posting

```
/apply https://boards.greenhouse.io/company/jobs/123456
```

Or paste the full text (use for LinkedIn, which blocks scraping):
```
/apply [paste job text here]
```

### Batch processing

1. Save job posting texts as `.txt` files in `jobs_inbox/`:
   ```
   jobs_inbox/Stripe_Senior_Data_Scientist.txt
   jobs_inbox/Anthropic_ML_Engineer.txt
   ```

2. Run:
   ```
   /apply-all
   ```

3. Review results in `outputs/ready/`

### Manual pipeline (step by step)

```
/job-analysis Stripe "Senior Data Scientist"
/cv-adaptation Stripe "Senior Data Scientist"
/cover-letter Stripe
/critic Stripe "Senior Data Scientist"
```

### Regenerate dashboard

```
/dashboard
```

## Output structure

```
outputs/
└── ready/
    └── Stripe_Senior_Data_Scientist/
        ├── analysis.json              # Fit score, gaps, skills classification
        ├── cv_Stripe_Senior_Data_Scientist.json     # Adapted CV as JSON
        ├── cv_Stripe_Senior_Data_Scientist.docx     # Rendered Word document
        ├── CV_Stripe_Smith.pdf                       # PDF version
        ├── cover_letter_Stripe_Senior_Data_Scientist.docx  # Cover letter
        └── critic_report_Stripe_Senior_Data_Scientist.json # Quality review
```

Move to `outputs/applied/` after submitting. Move to `outputs/discarded/` if rejected.

## Configuration

### Salary threshold

Edit `profile.json` → `preferences.min_salary` and `preferences.currency`:
```json
"preferences": {
  "min_salary": 150000,
  "currency": "USD"
}
```

Jobs published below this threshold are auto-skipped.

### Visa sponsorship

```json
"preferences": {
  "sponsorship_required": true
}
```

When enabled, job-analysis checks each posting for sponsorship signals and flags or auto-skips accordingly.

### Pre-screening rules

In `.claude/skills/apply-all/SKILL.md` → Step 1.5, customize the auto-skip and flag rules based on your preferences. The defaults skip: staff augmentation, pure analytics/BI roles, junior positions, and roles with hard stack gaps.

### Market salary ranges

In `.claude/skills/job-analysis/SKILL.md` → Step 3.7, update the reference salary ranges for your target market and currency.

## Project structure

```
.claude/
└── skills/
    ├── setup/          # Interactive onboarding — start here
    ├── job-analysis/   # Parse + classify + score
    ├── cv-adaptation/  # Adapt CV + generate .docx/.pdf
    ├── cover-letter/   # Generate + save cover letter .docx
    ├── critic/         # Quality review + AI flag detection
    ├── apply/          # Single-job entry point
    ├── apply-all/      # Batch orchestrator
    └── dashboard/      # HTML dashboard generator
assets/
├── cv/                 # Your base CV templates (cv_base_en.docx)
├── cover_letters_examples/  # Past letters (style reference)
├── knowledge_base/     # Synthesized personal knowledge base
└── google/             # OAuth credentials (not versioned)
jobs_inbox/             # Drop .txt job postings here
outputs/                # Generated CVs, cover letters, reports
```

## How it works

The pipeline uses a hierarchical knowledge base to ensure all generated content is grounded in documented facts:

```
profile.json            ← source of truth (what can be asserted)
    ↓
project_depth.md        ← technical context per project
    ↓
self_framing.md         ← honest gap/strength framing
    ↓
writing_voice.md        ← voice and style patterns
```

No fabrication is allowed — if a claim isn't backed by `profile.json` or `project_depth.md`, the critic agent flags it.

## Adapting for your situation

### For USA job seekers (visa sponsorship)

1. Set `sponsorship_required: true` in `profile.json` preferences
2. Update salary ranges in `job-analysis/SKILL.md` Step 3.7 to USD ranges
3. Remove Spanish pipeline if not needed (no action required — English is the default)

### For non-DS roles (engineers, analysts, PMs)

The framework is role-agnostic. Update:
- `profile.json` with your actual skills and experience
- Pre-screening rules in `apply-all/SKILL.md` to match your target roles
- Role types in `extract_skills.py` if you want differentiated thresholds for your role types

## Contributing

Issues, suggestions, and PRs welcome. This is a personal project shared as a template — if you build on it, a mention or link back is appreciated.

## License

MIT — use freely, attribution appreciated.
