import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from .common import ROOT, load_rows, evaluate
MODEL_PATH = ROOT / "ai_comparison" / "cancellation_logistic.joblib"

def train():
    rows = load_rows("train")
    model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), LogisticRegression(max_iter=1000, class_weight="balanced"))
    model.fit([r["text"] for r in rows], [r["theme"] for r in rows])
    return model

def save(model):
    joblib.dump(model, MODEL_PATH)
    return MODEL_PATH

def load():
    return joblib.load(MODEL_PATH)

def predict(model, texts):
    if not texts or any(not isinstance(t, str) or not t.strip() for t in texts):
        raise ValueError("Invalid feedback")
    probabilities = model.predict_proba(texts)
    indexes = probabilities.argmax(axis=1)
    labels = [str(model.classes_[i]) for i in indexes]
    scores = [float(probabilities[j, i]) for j, i in enumerate(indexes)]
    return labels, scores

if __name__ == "__main__":
    model = train()
    evaluate("logistic", lambda texts: predict(model, texts))
    path = save(model)
    print(f"Model saved: {path}")
    print(f"Model size: {path.stat().st_size / 1024:.1f} KB")
