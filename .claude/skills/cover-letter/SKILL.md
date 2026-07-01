---
name: cover-letter
description: Generates a personalized 250-350 word cover letter for a specific company and role, coherent with the adapted CV and aligned to the company's culture. Requires cv-adaptation to have run first.
disable-model-invocation: true
argument-hint: "[company]"
---

# Cover Letter Generation

## When to use this skill
Invoke with `/cover-letter [company]` when these already exist:
- `outputs/ready/{company}_{role}/analysis.json`
- `outputs/ready/{company}_{role}/cv_{company}_{role}.json`

If either is missing, run `/job-analysis` and `/cv-adaptation` first.

## Required inputs
- `outputs/ready/{company}_{role}/analysis.json`
- `outputs/ready/{company}_{role}/cv_{company}_{role}.json`
- Company context: ask user if not available
- `assets/knowledge_base/` — knowledge base (loaded in Step 0)
- `assets/cover_letters_examples/` — candidate's example letters (additional style reference)

## Execution sequence

### Step 0 — Load knowledge base
> **If this skill is invoked from inside `apply` or `apply-all`**: knowledge base is already loaded in session context — skip this step entirely.

Before any other action, read these files in order:

1. `profile.json` — master candidate record (skills, experience, projects, preferences, learning_in_progress)
2. `assets/knowledge_base/project_depth.md` — complete technical description of each project
3. `assets/knowledge_base/self_framing.md` — how the candidate describes themselves (honest framing of gaps and strengths)
4. `assets/knowledge_base/writing_voice.md` — candidate's voice patterns, tone, sentence structure, and vocabulary

These four files are the context from which the entire letter is generated. If any doesn't exist, notify the user before continuing.

### Step 1 — Verify inputs
Read `outputs/ready/{company}_{role}/analysis.json` and `outputs/ready/{company}_{role}/cv_{company}_{role}.json`.
If they don't exist, stop and indicate which skill to run first.

### Step 2 — Get company_context
If the user hasn't provided company context:
- Try to find public information (product, market, scale, known stack)
- If not found, ask the user: "Do you have any info about [company]? (mission, product, culture, known technical decisions)"
- If no context is available, continue focused on the candidate and mark output as "limited context"

### Step 3 — Generate cover letter in session
With the full knowledge base loaded, generate the cover letter body directly in this session. Do NOT use the `generate_cover_letter.py` script for generation.

**Apply all content and style rules in this document** (see following sections).

The generated text must:
- NOT include a greeting (the script adds it)
- NOT include a signature or sign-off (the script adds it)
- Be between 250 and 350 words

### Step 4 — Save the draft and run save_cover_letter.py
Once the text is generated, create the draft JSON file:

```json
{
  "text": "<generated body>",
  "company": "<company from analysis.json>",
  "role": "<role from analysis.json>",
  "language": "<language from analysis.json, default 'en'>",
  "output_dir": "outputs/ready/<company>_<role>"
}
```

Save this JSON as `outputs/ready/{company}_{role}/.cover_letter_draft.json` and run:

```bash
python .claude/skills/cover-letter/scripts/save_cover_letter.py \
  outputs/ready/{company}_{role}/.cover_letter_draft.json
```

### Step 5 — Validate result
Check the output:
- Word count between 250 and 350 words
- At least 1 concrete project with technologies and results mentioned
- Does not cite or paraphrase the posting text; the connection to requirements is implicit
- Does not start with a flashy or rhetorical opening
- Does not contradict the adapted CV
- No clichés: "passionate", "team player", "results-oriented", "proactive"
- Ends with a clear call to action
- Voice sounds like the candidate (see `writing_voice.md`), not generic AI

If word count is out of range, regenerate with an adjustment instruction before saving.

### Step 6 — Report
Indicate to user:
- Path of the generated .docx
- Word count
- Skills mentioned from the analysis

## Validation rules
- Length: 250–350 words (hard limit)
- Do not use first person more than 8 times
- Do not include salary expectations unless the posting explicitly requires it
- Must end with a clear call to action
- At least 1 concrete project with technologies and results
- The connection to role requirements must be implicit, never declared

## Opening and closing restrictions

**Opening: PROHIBITED to mirror the posting**
The first paragraph MUST NEVER:
- Quote the role title or its requirements as the reason for interest
- Explain why the role is relevant to the candidate using language from the posting
- Start with "I am looking for a role where..." followed by what the posting offers

The opening MUST establish who the candidate is and what they build professionally. Interest in the company is expressed with something real about the company (product, market, scale, technical decision), not by repeating what the posting says.

**Closing: PROHIBITED to describe what the role gives the candidate**
The final paragraph MUST NOT:
- Describe what the role offers the candidate
- Repeat posting attributes or language as motivation

The closing MUST express the candidate's direction: what they want to build in the future, what kind of impact they seek, what excites them about the technical domain or company domain. Without referencing the posting.

**Company references: always real, never from the posting**
When mentioning the company to express interest, use something concrete and real: business scale, product or service offered, public tech stack, market position, client type. NEVER repeat what the job posting says about the company or its internal descriptors ("diverse team", "fast-growing", "impact-driven").

## Additional restrictions

**Document language**
The cover letter language must match the original posting language. Read the `language` field from `analysis.json`: `"en"` → English, `"es"` → Spanish. The generated body must be entirely in that language.

**Mandatory greeting**
Every cover letter starts with a formal greeting (added automatically by `save_cover_letter.py`):
- English: "Dear [Company] Hiring Team,"
- Spanish: "Estimado equipo de [Company],"
The body generated by Claude must NOT include the greeting — the script adds it. Always, for any type of company.

**Em dash: PROHIBITED (GOLDEN RULE)**
The em dash "—" is completely prohibited in the cover letter body. No exceptions. Alternatives: semicolon (`;`), comma (`,`), or sentence rewrite. **Never replace with a colon (`:`) — also prohibited.** En-dash in numeric ranges (e.g., "2022–2025") is acceptable.

**Colon (`:`): PROHIBITED in body text (GOLDEN RULE)**
Colons are completely prohibited in the cover letter body. No exceptions.
Common patterns to eliminate:
- Stack enumeration: "I work with GCP: BigQuery, Cloud Composer" → "I work with GCP, using BigQuery and Cloud Composer"
- Expanded reformulation: "ownership is real: from scoping..." → "ownership is real from scoping..."
- Principle introduction: "one operating principle: models are useful..." → "the principle that models are useful..."
Alternatives: comma (`,`), period and new sentence, preposition ("with", "including", "where"), or direct rewrite.

**Prohibited explanatory phrases**
Do not include phrases that explain to the recruiter why the experience is relevant. The connection must be implicit. Prohibited examples: "maps directly to what this role requires", "which is exactly what you're looking for", "directly applicable to", "this aligns perfectly with", "directly relevant to". The recruiter makes that connection themselves.

**No fabricated business outcomes**
Only assert results documented in `profile.experience[]` or `profile.projects[]`. Use `project_depth.md` as reference for which metrics are validated.

**Skills without project backing = "in progress" framing**
Skills present in `profile.skills[]` that don't have backing in at least one achievement in `experience[]` or `projects[]` CANNOT be presented as tools used daily. If relevant to the role, use: "actively building experience with [skill]" or "deepening my work in [skill] as a natural extension of [related documented skill]".

**No date**
Never include a date in the cover letter — not in the header, not in the first sentence, not anywhere.

**Signature — do not duplicate contact data**
The generated body MUST NOT include signature, sign-off, or contact details. The signature is added automatically by `save_cover_letter.py`.

**Seniority narrative for Senior roles**
If the role title contains "Senior", the cover letter must include at least one reference to: technical leadership, mentoring, cross-functional scope, or expanded responsibility.

**Exact academic degree name**
Always use the exact name as documented in `profile.education[]`. Never paraphrase or abbreviate.

**No mirroring the posting's adjectives**
Never return the company's own adjectives as the reason for interest. Express genuine interest through concrete details of product, technology, or mission.

**No external narrator about the company**
Do not describe the company in third person and then connect to the candidate.
❌ "Company X operates at meaningful scale... The complexity creates exactly the kind of modeling challenges I find most engaging."
✅ "I'm interested in the complexity of a two-sided marketplace: matching supply and demand..." — first person from the first word, without a descriptive intro of the company, without AI bridge phrases.

## Error handling

| Error | Action |
|---|---|
| Adapted CV not found | Run `/cv-adaptation [company] [role]` first |
| `company_context` empty | Generate focused on candidate, mark as "limited context" |
| Word count out of range | Regenerate before running save script |
| Knowledge base not found | Notify user, continue with profile.json as minimum |

## Scripts available
- [`scripts/save_cover_letter.py`](scripts/save_cover_letter.py) — saves generated text as .docx with greeting and signature
- [`scripts/generate_cover_letter.py`](scripts/generate_cover_letter.py) — legacy: generation via Claude API (keep for compatibility with apply/apply-all if needed)
