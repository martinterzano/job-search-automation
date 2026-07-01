---
name: dashboard
description: Regenerates the HTML dashboard from the current Google Sheet tracker data. Use at any time to refresh the dashboard without running the full apply-all pipeline.
disable-model-invocation: true
---

# Dashboard — Regenerate

## When to use this skill
Invoke with `/dashboard` at any time to regenerate `outputs/dashboard.html` with current data from the Google Sheet tracker.

Does not require running `/apply-all`. Ideal for:
- Viewing the updated tracker after manually editing the Sheet
- Regenerating the dashboard after moving postings between states (ready → applied → discarded)
- Verifying that the dashboard reflects the latest data

---

## Step 1 — Run the generator

```bash
python .claude/skills/apply/scripts/generate_dashboard.py
```

The script:
1. Reads data from the "Active" and "Skip" sheets in the Google Sheet (`GOOGLE_SHEETS_SPREADSHEET_ID` from `.env`)
2. Calculates metrics (totals, average fit score, apply rate, score distribution, timeline)
3. Generates `outputs/dashboard.html`

---

## Step 2 — Report to user

Once executed, show:

```
Dashboard regenerated: outputs/dashboard.html

  Total analyzed:    {N}
  Avg fit score:     {avg}
  Apply rate:        {apply_rate}%

Open in browser to view the full dashboard.
```

---

## Prerequisites

- `GOOGLE_SHEETS_SPREADSHEET_ID` must be set in `.env`
- `assets/google/credentials.json` and `assets/google/token.json` must exist
- First time: follow `assets/google/SETUP.md`

---

## Error handling

| Error | Action |
|---|---|
| `GOOGLE_SHEETS_SPREADSHEET_ID` not found in .env | Indicate that `update_tracker.py` must run first, or add the ID manually |
| `credentials.json` not found | Indicate to follow `assets/google/SETUP.md` |
| Google Sheet has no data | Generate empty dashboard and inform user |
