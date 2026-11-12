# P2-A3 First Draft: Status and Roadmap

Team 4 (Undone). Final submission (P2-A4) is due **December 8, 2026**.

## Who owns what

The team split the six final-project parts as follows (agreed by message, week of Nov 2):

| Final-project part | Owner |
|---|---|
| 1. Product scope and user experience | Laasyasri Rangu |
| 2. Django application development | Ashok Chacko |
| 3. AI integration | Laasyasri Rangu |
| 4. Evaluation, testing and improvement | Laasyasri Rangu |
| 5. Deployment, cost and production readiness | Ashok Chacko |
| 6. Documentation and reproducibility | Ashok Chacko (README, setup); AI docs by Laasyasri |

## First-draft requirements: where each one is

| Requirement | Owner | Where |
|---|---|---|
| 1. Updated product scope (1 page) | Laasyasri | This repository, under docs folder (P2-A3_part1.pdf) |
| 2. Functional Django foundation | Ashok | This repository. See README "Features working in this draft". |
| 3. Initial AI implementation / plan | Laasyasri | *To be added by Laasyasri.* The Django hand-off point is ready (README, "AI functionality"). |
| 4. Development progress and roadmap | Both | This file |
| 5. GitHub submission with README | Ashok | This repository |

### Requirement 2 checklist (verified by `python manage.py test`, 29 tests passing)

- [x] Functional Django project (`undone_project`) with split settings
- [x] At least one app (`feedback`)
- [x] At least two meaningful models: `Dataset`, `FeedbackResponse`, `Theme`
- [x] Relationships: User→Dataset, Dataset→FeedbackResponse, Dataset→Theme, Theme→FeedbackResponse
- [x] Working views and templates: function-based and class-based views, template inheritance from `base.html`, and shared includes
- [x] Forms with validation: CSV upload, column mapping, theme, dataset edit and sign-up
- [x] Database-backed workflow: upload CSV → view validates → rows saved → dashboard shows aggregates
- [x] Also done early: login and protected routes, per-user data isolation, JSON API, CSV export, search and filters, charts

## Roadmap to December 8

Dates marked *proposed* have not yet been agreed by the whole team.

| Task | Current status | Responsible member | Expected completion |
|---|---|---|---------------------|
| Django core features | **Done for draft.** Upload, mapping, dashboard, responses, theme CRUD, export. Remaining: trend view by theme and plan-vs-plan comparison page (wireframes 7 and 8), and the analysis status page (wireframe 4). | Ashok | Nov 23 *(proposed)* |
| Database and APIs | **Done for draft.** 3 models, migrations, summary JSON API. Remaining: analysis-status API for the processing page, and per-theme trend data in the API. | Ashok | Nov 23 *(proposed)* |
| AI integration | Not started in this repository. Django hand-off functions are ready and tested (`responses_for_analysis`, `apply_theme_assignments`). | Laasyasri | Nov 25 *(proposed)* |
| Evaluation and testing | Django test suite: 29 tests passing. AI evaluation (5 realistic tests, failure analysis, before/after improvement) not started. | Laasyasri (AI evaluation), Ashok (Django tests) | Dec 2 *(proposed)*  |
| Deployment | Not started. Production settings, WhiteNoise and the secret-key check are already in place. Next: PythonAnywhere deploy, HTTPS settings, cost comparison, 10k-DAU scalability write-up. | Ashok | Dec 1 *(proposed)*  |
| Documentation | README with setup, environment, database, run and test steps is done. Remaining: `README_AI.md` (Laasyasri), deployment section, final screenshots. | Ashok (README), Laasyasri (README_AI.md) | Dec 6 *(proposed)*  |

## Dependencies and risks

- **AI integration blocks evaluation, and both block the demo video's AI segment (1:45–2:30).** The model must run inside Django by roughly Nov 30 to leave time for Part 4 testing.
- **AI deployment limitations.** We are currently using TF-IDF with Logistic Regression because it requires less storage than Qwen3-0.6B or MiniLM. The trained model is approximately 44.9 KB and does not require PyTorch. We still need to verify that Scikit-learn and the full Django application fit within PythonAnywhere's free storage limit. The model has only been tested locally and still needs Django integration. 
- The AI processing page (wireframe 4) needs a status field. It already exists: `Dataset.status` has Awaiting analysis / Analyzing / Analyzed / Failed.


## TO-DO
Remaining: test on more realistic customer feedback with different writing styles and multiple cancellation reasons. Complete independent evaluation and Django testing.