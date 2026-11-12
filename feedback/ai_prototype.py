from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

feedback = [
    "The subscription is too expensive",
    "The monthly price is too high",
    "I cannot afford the subscription",
    "The price keeps increasing",
    "This service costs too much",

    "The app keeps crashing",
    "The website has too many bugs",
    "The product does not work properly",
    "I keep getting errors",
    "The application is very slow",

    "Customer support never responded",
    "The support team was unhelpful",
    "Nobody answered my questions",
    "Customer service was terrible",
    "The support staff did not help",

    "I do not use this anymore",
    "I rarely open the app",
    "I no longer need this subscription",
    "I stopped using the service",
    "I barely use my account"
]

themes = (
    ["Pricing"] * 5
    + ["Product Issues"] * 5
    + ["Customer Support"] * 5
    + ["Lack of Use"] * 5
)

model = make_pipeline(
    TfidfVectorizer(ngram_range=(1, 2)),
    LogisticRegression(max_iter=1000)
)
model.fit(feedback, themes)
test_feedback = [
    "The subscription costs too much money",
    "The app crashes every time I open it",
    "Customer support ignored my request",
    "I don't need this service anymore"
]

for response in test_feedback:
    theme = model.predict([response])[0]
    confidence = max(model.predict_proba([response])[0])
    print("Feedback:", response)
    print("Predicted theme:", theme)
    print("Confidence:", round(confidence, 2))
    print()
