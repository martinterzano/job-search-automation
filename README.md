# Job Search Automation — Claude Code Skills Template

An agentic pipeline for automating job search. Built with [Claude Code Skills](https://docs.anthropic.com/en/docs/claude-code/skills).

Drop a job posting URL or text, get a tailored CV and cover letter in minutes.

---

## What this is

Built during an active job search to test whether Claude Code agents could make the application process faster without reducing quality. Looking for a job is time-consuming. When you cherry-pick roles that genuinely fit you, you still run into constant friction: companies mislabelling roles, non-negotiable stack requirements that differ by one cloud provider, seniority bars set wrong for the actual day-to-day, or a role title that matches but a job description that doesn't. Filtering and applying at quality takes more effort than most people expect. The first version ran on the builder's own applications. It was designed as a template from the start because the logic is candidate-agnostic. All personal data lives in files that the pipeline reads but does not own.

A job application pipeline has three distinct failure modes. The first is wasted effort (spending two hours on an application for a role that would have been auto-screened in 30 seconds). The second is low quality (a cover letter that sounds like every other cover letter because it was generated without context about the candidate). The third is an unadapted CV that never passes the ATS (Applicant Tracking System) filters that most companies use today. This pipeline targets all three.

**Who it is for.** Anyone in active job search who receives enough volume to benefit from automation and wants to maintain a quality bar without doing it entirely by hand. The template ships with examples from a Data Science search, but the framework is role-agnostic — see *Adapting for your situation* at the end.

**What it is not.** A one-click apply tool. A career management platform. A replacement for preparation. A system that works without your honest, detailed input about your own experience.

## What it does

1. **Parses** job postings (URL or pasted text) and classifies requirements as Must / Should / Nice-to-Have
2. **Scores** candidate fit (0–100) using a weighted algorithm with semantic aliases — "React" matches "frontend framework", "PostgreSQL" matches "relational database"
3. **Pre-screens** in batch — auto-skips body shops, junior roles, off-stack positions, and flags borderline cases for your review before running the expensive pipeline
4. **Adapts** your CV, prioritising the most relevant experience for each posting, grounded entirely in your `profile.json`
5. **Generates** cover letters in your authentic voice, synthesised from samples of your real writing
6. **Critiques** outputs automatically. Catches AI flags, fabrications, and rule violations. Proposes corrections in HITL mode; applies only non-negotiable fixes in AUTO mode
7. **Tracks** everything in Google Sheets and generates an HTML analytics dashboard

Every component is customisable: scoring weights, pre-screening rules, salary thresholds, target language, CV format, and cover letter constraints. These live in `SKILL.md` files and `profile.json` — no hardcoded logic. The defaults ship as a working example; your setup replaces them.

All outputs go to `outputs/ready/{company}_{role}/` — CV (.docx + .pdf), cover letter (.docx), and a critic report.

## What it doesn't do

- **No automated submissions.** The pipeline generates materials; you decide what to submit. No portals are filled, no buttons are clicked automatically.
- **No LinkedIn scraping.** LinkedIn and many other platforms block programmatic access. Save the posting text as a `.txt` file in `jobs_inbox/` instead.
- **No autonomous company research.** The pipeline uses the posting text you provide and your knowledge base. It fetches one page from the company website as context, and stops there.
- **No output quality without input quality.** The depth of the CV and cover letter is directly proportional to the depth of `profile.json`, `project_depth.md`, and `self_framing.md`. Thin input produces thin output.
- **No model portability.** The skills are written for Claude Code and use its context and tool interfaces. Porting to another model requires rewriting the `SKILL.md` files.
- **No replacement for interview preparation.** The critic flags AI patterns and fabrications, but it cannot substitute for gaps in your actual experience or prepare you for a technical interview. It does flag those gaps so you can address them.

## Architecture & design decisions

### Skills as bounded agents, not a monolith

Each skill (`job-analysis`, `cv-adaptation`, `cover-letter`, `critic`) has its own `SKILL.md` with a complete, self-contained instruction set. They can run standalone (`/cv-adaptation Stripe "Senior DS"`) or be orchestrated in sequence by `apply-all`. The separation enforces a discipline: each agent has one job, a defined input schema, and a defined output schema. When something goes wrong, the fault is localised to one skill rather than hidden inside a single long prompt.

`apply-all` is the orchestrator, not the brain. It scans the inbox, runs pre-screening, sequences the agents, and assembles the summary. It does not contain job-specific reasoning. That lives in the individual skills.

### The knowledge base is the source of truth, not the model

The four-file knowledge base (`profile.json`, `project_depth.md`, `self_framing.md`, `writing_voice.md`) forms a contract between the candidate and the pipeline. Every agent that produces output reads these files before reasoning. The contract has one rule: if a claim is not backed by `profile.json` or `project_depth.md`, it cannot appear in a CV or cover letter. The critic agent enforces this at the end of every run by cross-referencing generated content against the source of truth.

This was the most important structural decision. Without it, the pipeline produces plausible-sounding fabrications that get caught in interviews. With it, the model is constrained to synthesis and framing, not invention.

### Pre-screening before the expensive pipeline

`apply-all` classifies every posting across five dimensions (company type, role core, seniority, stack gaps, domain) before running any agent. Staff augmentation firms, pure analytics roles, and junior postings are auto-skipped. Startups, consulting firms, and roles with partial stack gaps are flagged for human confirmation. The full pipeline only runs on confirmed candidates.

The cost of skipping a false negative is low (a missed application). The cost of running the full pipeline on a body shop posting is non-zero and produces an output that will never be used. Pre-screening inverts the default.

### Two operating modes for the critic

**AUTO mode** (inside `apply` or `apply-all`): applies only changes that are deterministic and non-negotiable. Prohibited phrases in the blacklist, claims with no backing in `profile.json`, factual inconsistencies between CV and cover letter, explicit opening clichés. Style, tone, and narrative structure are documented in the report but not touched. The batch does not pause.

**HITL mode** (`/critic [company] [role]`): proposes all changes and waits for explicit approval before modifying anything. The candidate sees the recruiter perspective and decides what to accept, reject, or modify.

Auto-applying a blacklisted cliché removal is always correct. Auto-applying a tonal preference is not. The two modes reflect the difference between a rule with no exceptions and a judgment call.

### SKILL.md propagation: the pipeline learns from its own errors

When the critic identifies a systemic problem (a missing rule or a contradiction in an existing instruction, not a one-off model error), it can edit the `cover-letter/SKILL.md` or `cv-adaptation/SKILL.md` directly. Only additive changes in AUTO mode: new rules added, existing contradictions corrected. The pipeline accumulates constraints over time from real application runs rather than from upfront specification.

Each manual correction logged to `writing_voice/learnings.md` is loaded by every subsequent run, narrowing the gap between what the model produces and what the candidate would actually write.

### Output structure as an audit trail

Every application produces a folder with a fixed schema: `analysis.json`, `cv_{company}_{role}.json`, `cv_{company}_{role}.docx`, `cover_letter_*.docx`, `critic_report_*.json`. The Google Sheets tracker and HTML dashboard are derived views over this structure. The JSON files are the primary record.

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

No fabrication is allowed — if a claim is not backed by `profile.json` or `project_depth.md`, the critic agent flags it.

## How the template is designed for reuse

Three principles shaped the design:

**Personal data is completely outside the codebase.** Everything specific to you (CV, cover letters, profile, knowledge base, Google credentials) is either excluded by `.gitignore` or lives in template files with no real data. Fork the repo, add your own files, and you will not accidentally commit personal information.

**Two onboarding paths.** `/setup all` walks you through creating all personal files interactively — Claude asks questions and generates the files from your answers. If you prefer to edit files directly, every template in `assets/knowledge_base/` contains instructions at the top explaining what to write and why. Both paths produce the same file structure.

**The pre-screening rules are the first thing to customise.** The auto-skip and flag logic in `apply-all/SKILL.md` Step 1.5 reflects the builder's own search criteria: role type, company type, seniority level, stack gaps. The defaults are a working example, not a prescription. Before running a real batch, review them against your own situation. Getting them wrong in the auto-skip direction is low-cost (you can always process a skipped posting manually). Getting them wrong in the process direction wastes pipeline runs on postings you would have discarded anyway.

---

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
git clone https://github.com/martinterzano/job-search-automation
cd job-search-automation

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## Setup (first time)

Two options — pick whichever fits your style:

### Option A — Interactive onboarding (recommended)

Open the project folder in Claude Code and run:

```
/setup all
```

This guided flow creates:
1. `profile.json` — your master candidate record (skills, experience, projects, preferences)
2. `assets/knowledge_base/writing_voice.md` — your voice and tone synthesized from your past writing
3. `assets/knowledge_base/self_framing.md` — honest assessment of your strengths and gaps
4. `assets/knowledge_base/project_depth.md` — technical depth for each project

### Option B — Manual setup

Prefer to edit files directly? Every file is self-documented:

1. Copy `profile.template.json` → `profile.json` and fill in your data. Each field has a `_comment` explaining what to put there.
2. Open `assets/knowledge_base/writing_voice.md`, `self_framing.md`, and `project_depth.md` — each file contains instructions at the top explaining what to write and how to structure it.

---

Then add your base CV to `assets/cv/`:
- Name it exactly `cv_base_en.docx` (English) and `cv_base_es.docx` (Spanish, optional)

### Google Sheets setup (optional but recommended)

```
See assets/google/SETUP.md for step-by-step instructions
```

After setup, the tracker auto-creates on first run of `update_tracker.py`.

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

1. Save job posting texts as `.txt` files in `jobs_inbox/`
2. Run `/apply-all`
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
        ├── analysis.json
        ├── cv_Stripe_Senior_Data_Scientist.json
        ├── cv_Stripe_Senior_Data_Scientist.docx
        ├── CV_Stripe_Smith.pdf
        ├── cover_letter_Stripe_Senior_Data_Scientist.docx
        └── critic_report_Stripe_Senior_Data_Scientist.json
```

Move to `outputs/applied/` after submitting. Move to `outputs/discarded/` if rejected.

## Configuration

### Salary threshold

Edit `profile.json` → `preferences.min_salary`:
```json
"preferences": {
  "min_salary": 150000,
  "currency": "USD"
}
```

### Pre-screening rules

In `.claude/skills/apply-all/SKILL.md` → Step 1.5, customise the auto-skip and flag rules. The defaults ship as a working example for one specific search. Review and adjust them before running your first real batch.

### Market salary ranges

In `.claude/skills/job-analysis/SKILL.md` → Step 3.7, update the reference salary ranges for your target market and currency.

## Project structure

```
.claude/
└── skills/
    ├── setup/          # Interactive onboarding
    ├── job-analysis/   # Parse + classify + score
    ├── cv-adaptation/  # Adapt CV + generate .docx/.pdf
    ├── cover-letter/   # Generate + save cover letter .docx
    ├── critic/         # Quality review + AI flag detection
    ├── apply/          # Single-job entry point
    ├── apply-all/      # Batch orchestrator
    └── dashboard/      # HTML dashboard generator
assets/
├── cv/                 # Your base CV templates
├── cover_letters_examples/  # Past letters (style reference)
├── knowledge_base/     # Synthesized personal knowledge base
└── google/             # OAuth credentials (not versioned)
jobs_inbox/             # Drop .txt job postings here
outputs/                # Generated CVs, cover letters, reports
```

## Adapting for your situation

### For USA job seekers (visa sponsorship)

1. Set `sponsorship_required: true` in `profile.json` preferences
2. Update salary ranges in `job-analysis/SKILL.md` Step 3.7 to USD ranges
3. Remove Spanish pipeline if not needed (no action required — English is the default)

### For non-DS roles (engineers, analysts, PMs)

The framework is role-agnostic. Update `profile.json` with your actual skills, pre-screening rules in `apply-all/SKILL.md` for your target roles, and role types in `extract_skills.py` if you want differentiated thresholds.

## Contributing

Issues, suggestions, and PRs welcome. This is a personal project shared as a template — if you build on it, a mention or link back is appreciated.

## License

MIT — use freely, attribution appreciated.
