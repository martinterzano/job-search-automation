---
name: apply
description: Entry point for a single job posting. Fetches the text (URL or paste), saves it to jobs_inbox/, and delegates to apply-all to run the full pipeline.
disable-model-invocation: true
argument-hint: "[job_url | job_text]"
---

# Apply — Single Job Pipeline

## When to use this skill
Invoke with `/apply [url | text]` when you have a single job posting to process.
`/apply-all` works the same way if the `.txt` is already in `jobs_inbox/` — you can use it directly.

Examples:
```
/apply https://boards.greenhouse.io/company/jobs/123456
/apply https://jobs.lever.co/company/data-scientist
```

> **LinkedIn**: blocks automatic fetch. Paste the full job text directly as the argument.

---

## Step 1 — Get the job text

**If it's a URL** (starts with `http`):
Use `WebFetch` to get the page content.
Extract relevant text: company, role, description, requirements.

**If it's raw text**:
Use the text as-is.

**If no argument provided**:
Ask: "Do you have the job URL or would you like to paste the text directly?"

---

## Step 2 — Save to jobs_inbox/

Extract `{company}` and `{role}` from the posting content.
If they cannot be reliably inferred, ask the user before continuing.

Save to:
```
jobs_inbox/{company}_{role}.txt
```

---

## Step 3 — Delegate to apply-all

Read and follow **in full** the instructions in `.claude/skills/apply-all/SKILL.md`.

apply-all will detect the newly saved file as pending and execute the full pipeline
(Step 0 KB pre-load → Step 1 inbox scan → Step 2 per-job pipeline → Step 3 summary).

---

## Error handling

| Error | Action |
|---|---|
| URL not accessible (LinkedIn, login required) | Ask user to paste the job text |
| Company or role not inferable | Ask before saving the file |
| `profile.json` not found | apply-all will detect it and stop with a clear message |
