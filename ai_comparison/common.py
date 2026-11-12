import csv
from pathlib import Path
from time import perf_counter
from sklearn.metrics import accuracy_score, f1_score, classification_report
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "sample_data"
RESULTS = ROOT / "results"

def load_rows(split):
    with (DATA / f"{split}.csv").open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    if not rows or any(not r.get("text", "").strip() or not r.get("theme", "").strip() for r in rows):
        raise ValueError("Missing or invalid training data")
    return rows

def evaluate(name, predict):
    rows = load_rows("test")
    texts = [r["text"] for r in rows]
    expected = [r["theme"] for r in rows]
    start = perf_counter()
    predicted, scores = predict(texts)
    elapsed = perf_counter() - start
    if len(predicted) != len(rows) or len(scores) != len(rows):
        raise ValueError("Incorrect number of predictions")
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / f"{name}_predictions.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "text", "expected_theme", "predicted_theme", "score", "correct"])
        for row, theme, score in zip(rows, predicted, scores):
            writer.writerow([row["id"], row["text"], row["theme"], theme, round(float(score), 4), int(row["theme"] == theme)])
    print(f"\nModel: {name}")
    print(f"Accuracy: {accuracy_score(expected, predicted):.3f}")
    print(f"Macro F1: {f1_score(expected, predicted, average='macro'):.3f}")
    print(f"Prediction time: {elapsed:.3f} seconds")
    print(f"Average per response: {elapsed / len(rows) * 1000:.2f} ms")
    print(classification_report(expected, predicted, zero_division=0))
    print(f"Saved results: {path}")
