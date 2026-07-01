# Project Depth — [CANDIDATE_NAME]

## How to generate this file

Run `/setup depth` to have Claude walk you through each of your projects in detail. This file is the technical specification that ensures CVs and cover letters describe your projects accurately — with the right level of detail and without over-claiming.

**Why this matters**: Generic project descriptions get filtered out. Specific, verifiable details (architecture, scale, production status, your exact ownership) make the difference between a CV that passes and one that gets ignored. This file is also the guard against fabrication — if a detail isn't documented here, it shouldn't appear in a CV or cover letter.

---

## What this file should contain (after running /setup depth)

For each significant project in your profile, document:

---

### [Project Name] — [Year]

**Context**: Personal project / Professional (Company name) / Academic (Institution)

**Business problem**: What problem did this project solve? Who uses the output?

**Your ownership**: Sole owner / Lead (X% of work) / Contributor (~XX%)

**Algorithm/approach**: What ML algorithm(s) did you use? Why that choice over alternatives?

**Architecture**:
- Data sources
- Feature engineering approach (manual, automated, embeddings, RFM, etc.)
- Training methodology (train/test split, OOT validation, cross-validation, etc.)
- Model serving approach (batch scoring, real-time API, none)

**Scale**:
- Data size (approximate: number of rows, features, time span)
- Scoring frequency (weekly batch, daily, real-time, etc.)
- Infrastructure (GCP Vertex AI, AWS SageMaker, local, etc.)

**Production status**: In production / In development / Proof of concept / Academic

**Key outcomes**: What changed because of this model? (outperformed baseline, reduced X, improved Y)

**Metrics (internal use only)**:
Document the actual metrics here for reference. The framing rules below specify which ones to use externally.

**Framing rules** (how to describe this in CV/cover letter):
- MENTION: [outcome that's meaningful to a recruiter — scale, production status, methodology, business impact]
- AVOID: [technical metrics that are opaque to recruiters — e.g., specific AUC values, RMSE, proprietary metrics]
- CLAIM CAREFULLY: [ownership framing — e.g., "contributor role ~35%", "sole owner"]

**Prohibited claims**:
List anything about this project that must NEVER appear in CVs/cover letters:
- Outcomes not yet verified or still in progress
- Metrics where you were not the primary contributor
- Anything that would be an overstatement of your role

---

## Template — Copy for each project

### [PROJECT_NAME] — [YEAR]

**Context**: [Personal / Professional at COMPANY_NAME / Academic at INSTITUTION]

**Business problem**: [ONE_SENTENCE]

**Your ownership**: [OWNERSHIP_PERCENTAGE_AND_ROLE]

**Algorithm/approach**: [ML_ALGORITHM_AND_WHY]

**Architecture**:
- Data: [DATA_SOURCES_AND_SIZE]
- Features: [FEATURE_ENGINEERING_APPROACH]
- Validation: [TRAIN_TEST_OOT_CROSSVAL]
- Serving: [BATCH_REALTIME_NONE]

**Scale**: [ROWS, FEATURES, FREQUENCY, INFRA]

**Production status**: [IN_PRODUCTION / IN_DEVELOPMENT / POC / ACADEMIC]

**Key outcomes**: [BUSINESS_OUTCOME_WITHOUT_OPAQUE_METRICS]

**Metrics (internal)**:
- [METRIC_NAME]: [VALUE] — [USE / DO_NOT_USE externally]

**Framing rules**:
- MENTION: [WHAT_TO_HIGHLIGHT]
- AVOID: [WHAT_TO_OMIT]

**Prohibited claims**: [ANYTHING_THAT_CANNOT_BE_CLAIMED]
