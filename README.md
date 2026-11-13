# Undone: AI-Powered Subscription Cancellation Feedback Analyzer

**Team 4 (Team Undone):** Ashok Chacko (achac), Laasyasri Rangu (lrangu2)
INFO 490 MG, Fall 2026, Project 2

Undone helps subscription businesses understand **why customers cancel**. A user uploads a CSV of cancellation feedback; Undone stores each response, lets the user group responses into themes (AI grouping is in progress), and shows the most common reasons, how cancellations change month to month, and how plans compare.

> **Status: first draft (P2-A3, Nov 9).** The Django foundation is working end to end. Automatic AI theme detection is not built yet; see [Development roadmap](docs/P2-A3_roadmap.md) and the [AI integration contract](#ai-functionality).

## Features working in this draft

| Feature | What it does | Where |
|---|---|---|
| Accounts | Sign up, log in, log out. Every dataset page is private to its owner. | `/signup/`, `/accounts/login/` |
| CSV upload, step 1 | Upload a CSV. It's rejected with a clear message if it's not `.csv`, not UTF-8, empty, has duplicate or blank headers, or is over 5 MB / 5,000 rows. | `/datasets/upload/` |
| Column mapping, step 2 | Choose which column is the feedback text (required), date, plan, and customer group. Columns are pre-selected by name, and the first 5 rows are previewed. | `/datasets/<id>/map/` |
| Import report | Rows with empty feedback are skipped, and unreadable dates are left blank. The user is told how many of each and which rows. | flash messages |
| Dashboard | KPI cards, responses by theme, cancellations per month, and responses by plan. Built with ORM aggregation and charted from the JSON API. | `/datasets/<id>/` |
| Response explorer | Search the feedback text, filter by plan and theme (including "Unassigned"), with 25 per page. | `/datasets/<id>/responses/` |
| Themes (CRUD) | Create, rename and delete themes. Assign each response to a theme. Deleting a theme un-assigns its responses but never deletes them. | dashboard and responses pages |
| CSV export | Download every response with its theme. | `/datasets/<id>/export.csv` |
| JSON API | Summary statistics for one dataset. Returns `401` when signed out and `404` for other users' datasets. | `/api/datasets/<id>/summary/` |

## Tech stack

Python 3.11+ (tested on 3.14), Django 5.2 LTS, SQLite, WhiteNoise for static files, and Chart.js 4.4 (loaded from cdnjs).

## Setup

```bash
git clone <repository-url> undone
cd undone
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Environment variables

Copy the example file and set a secret key:

```bash
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

Paste the printed key into `.env` as `SECRET_KEY=...`. `.env` is git-ignored. Never commit it.

| Variable | Required | Meaning |
|---|---|---|
| `SECRET_KEY` | yes | Django secret key. Production refuses placeholder or `django-insecure-` keys. |
| `ALLOWED_HOSTS` | production | Comma-separated host names, e.g. `yourname.pythonanywhere.com` |
| `DEMO_PASSWORD` | no | Password for the `load_demo` user. If unset, you're prompted. |

### Database

`db.sqlite3` is **not** committed. Each developer creates their own:

```bash
python manage.py migrate
python manage.py load_demo --username demo     # optional: demo user + sample data
python manage.py createsuperuser               # optional: for /admin/
```

`load_demo` imports [`sample_data/sample_cancellations.csv`](sample_data/sample_cancellations.csv): 46 **synthetic** rows the team wrote for testing. They are not real customer data. One row deliberately has empty feedback and one has an unreadable date, so the import warnings are visible.

### Run

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>, then sign up, or log in as `demo`.

**Try the workflow:** Upload → choose `sample_data/sample_cancellations.csv` → check the column mapping → Import → Dashboard → **+ New theme** ("Pricing") → Responses → search "expensive" → set each row's theme → back to Dashboard to see the chart change → Export CSV.

### Tests

```bash
python manage.py test
```

29 tests cover CSV parsing and validation, the import, model rules, sign-in protection, **ownership isolation** (every dataset URL returns 404 to other users), the full upload-to-dashboard workflow, theme CRUD, search and filters, the JSON API and CSV export.

### Production mode (locally)

```bash
python manage.py collectstatic --settings=undone_project.settings.production
python manage.py runserver --settings=undone_project.settings.production
```

Production mode needs `ALLOWED_HOSTS` and a real `SECRET_KEY` in `.env`. Run `collectstatic` **with** the production settings, or the hashed static files are not written.

## Project layout

```
undone_project/settings/   base.py (shared), development.py (DEBUG on), production.py (DEBUG off)
feedback/models.py         Dataset, Theme, FeedbackResponse
feedback/services.py       CSV parsing, row import, AI hand-off functions
feedback/forms.py          upload, column mapping, theme, dataset and sign-up forms
feedback/views.py          pages, CSV export, JSON API
feedback/templates/        base.html, plus one template per page
feedback/tests.py          test suite
sample_data/               synthetic demo CSV
docs/                      P2-A2 idea and wireframes, roadmap, team notes
```

### Data model

```
User 1──* Dataset 1──* FeedbackResponse *──0..1 Theme *──1 Dataset
```

- `Dataset.owner` uses **CASCADE**: deleting an account removes that user's customer feedback instead of leaving it orphaned.
- `FeedbackResponse.theme` uses **SET_NULL**: deleting a theme un-assigns its responses instead of deleting feedback.
- Dataset names are unique per owner, and theme names are unique per dataset (database constraints).

## AI functionality

Automatic theme detection is **not implemented yet** (owner: Laasyasri, Part 3). The Django side is ready for it. The AI step needs only these two functions in `feedback/services.py`:

```python
responses_for_analysis(dataset)              # -> [(response_id, text), ...]
apply_theme_assignments(dataset, {response_id: (theme_name, confidence), ...})
```

`apply_theme_assignments` creates themes marked "Detected by AI", ignores any id that is not in the dataset, and marks the dataset **Analyzed**. Its behavior is covered by `AIHandOffTests`. The model, its preprocessing and its evaluation will be documented in `README_AI.md`.

### Initial AI prototype (P2-A3)

The initial AI implementation uses TF-IDF with Logistic Regression through Scikit-learn to classify customer cancellation feedback.

The implementation plan and experiment results are documented in [P2-A3 AI Implementation](docs/P2-A3_ai_implementation.md).

The model was trained using 92 synthetic cancellation responses and evaluated on 32 development test responses. It achieved 90.6% accuracy with a macro F1 score of 0.905. These results are from synthetic data and do not represent verified real-world accuracy.

To reproduce the experiment, install the dependencies using `pip install -r requirements.txt` and run:

```bash
python -m ai_comparison.logistic_model
```

The training data is in `sample_data/train.csv` and the test data is in `sample_data/test.csv`.

The trained model is saved to `ai_comparison/cancellation_logistic.joblib`. Predictions are saved to `results/logistic_predictions.csv`.

Automatic theme detection has not been connected to Django yet. This is planned for the final project.


## Documentation

- [docs/P2-A3_roadmap.md](docs/P2-A3_roadmap.md): first-draft status and the roadmap to Dec 8
- [docs/notes/notes.txt](docs/notes/notes.txt): weekly team notes
- [docs/wireframes/](docs/wireframes/) and [docs/Undone_Project_Idea_Description.pdf](docs/Undone_Project_Idea_Description.pdf): P2-A2 submission
