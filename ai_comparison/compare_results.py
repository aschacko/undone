import csv
from sklearn.metrics import accuracy_score, f1_score
from .common import RESULTS

def read(name):
    path = RESULTS / f"{name}_predictions.csv"
    if not path.exists():
        raise FileNotFoundError(f"Run {name}_model.py first")
    with path.open(newline="", encoding="utf-8") as file:
        return {r["id"]: r for r in csv.DictReader(file)}

def main():
    logistic = read("logistic")
    minilm = read("minilm")
    if logistic.keys() != minilm.keys():
        raise ValueError("Test datasets do not match")
    rows = list(logistic.values())
    expected = [r["expected_theme"] for r in rows]
    for name, data in [("Logistic Regression", logistic), ("MiniLM", minilm)]:
        predictions = [data[r["id"]]["predicted_theme"] for r in rows]
        accuracy = accuracy_score(expected, predictions)
        f1 = f1_score(expected, predictions, average="macro")
        print(f"{name}: Accuracy = {accuracy:.3f}, Macro F1 = {f1:.3f}")
    print("\nDifferent predictions:")
    for row in rows:
        a = logistic[row["id"]]["predicted_theme"]
        b = minilm[row["id"]]["predicted_theme"]
        if a != b:
            print(f"{row['text']} | Expected: {row['expected_theme']} | Logistic: {a} | MiniLM: {b}")

if __name__ == "__main__":
    main()
