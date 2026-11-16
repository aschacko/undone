from functools import lru_cache
from pathlib import Path
import joblib
from django.db import transaction
from .models import Dataset
from .services import responses_for_analysis, apply_theme_assignments

MODEL_PATH = Path(__file__).resolve().parent.parent / "ai_comparison" / "cancellation_logistic.joblib"

@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.is_file():
        raise FileNotFoundError("Trained AI model was not found.")
    return joblib.load(MODEL_PATH)

def analyze_dataset(dataset):
    if dataset.status == Dataset.Status.MAPPING:
        raise ValueError("Import the feedback before running AI analysis.")
    responses = responses_for_analysis(dataset)
    assigned = set(dataset.responses.filter(theme__isnull=False).values_list("id", flat=True))
    pending = [(response_id, text) for response_id, text in responses if response_id not in assigned and isinstance(text, str) and text.strip()]
    if not pending:
        return 0
    model = load_model()
    probabilities = model.predict_proba([text for _, text in pending])
    assignments = {}
    for (response_id, text), row in zip(pending, probabilities):
        index = int(row.argmax())
        theme = str(model.classes_[index])
        confidence = float(row[index])
        if theme and 0 <= confidence <= 1:
            assignments[response_id] = (theme, confidence)
    if not assignments:
        raise ValueError("The AI model did not return any valid predictions.")
    with transaction.atomic():
        return apply_theme_assignments(dataset, assignments)
