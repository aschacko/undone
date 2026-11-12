# P2-A3: Initial AI Implementation Plan

**Team 4: Undone**

## Proposed AI Feature

Our AI feature for Undone is automatic cancellation theme detection. The model will analyze customer cancellation feedback and identify the main reason why someone canceled their subscription. This is useful because businesses can receive a lot of feedback and manually organizing every response takes time. The AI will assign themes to the responses so businesses can understand which problems are causing customers to leave.

## Model Selection

I decided to use TF-IDF with Logistic Regression through Scikit-learn. TF-IDF converts customer feedback into numerical features and Logistic Regression learns patterns from labeled examples to predict a cancellation theme.

I chose this model because Undone mainly needs text classification instead of text generation. It is also lightweight and does not require PyTorch or a GPU. This makes it easier to deploy and maintain compared to larger language models.

I originally considered Qwen3-0.6B because I had used it for my ClassCompass assignment. I also considered all-MiniLM-L6-v2 because it can compare sentences based on their meaning. However, both would require more storage and dependencies. Since we are planning to deploy on PythonAnywhere I decided to continue with Logistic Regression because it should be easier to run with the free plan's storage limits.

The model is free to use and does not require an external AI API. This also means customer feedback can be processed locally on the application server instead of being sent to another service.

## AI Input and Output

The input will be customer cancellation feedback uploaded through a CSV file. Undone already has a working CSV upload feature that stores the responses in the Django database.

The model will read each response and predict one of four cancellation themes. These themes are Pricing, Product Issues, Customer Support and Lack of Use.

The output will be the predicted theme and a confidence score. For example, if a customer says their subscription is too expensive the model should predict Pricing. The results will eventually be saved in the database and displayed on the dashboard so businesses can see the most common cancellation reasons.

## AI Workflow and Django Integration

The AI will connect to the existing Django application through `feedback/services.py`. The function `responses_for_analysis(dataset)` retrieves the customer feedback along with its response ID.

The feedback will be processed using the saved TF-IDF vectorizer and Logistic Regression model. The model will then predict a theme for each response and return its estimated probability.

The predictions will be checked before being saved. Responses with missing text or uncertain predictions will need to be handled separately so the application does not automatically assign incorrect themes.

The function `apply_theme_assignments()` will save the predictions to the Django database. Once the integration is complete the results will appear on the dashboard and users will be able to review the assigned themes.

The planned workflow is:

**CSV Upload → Django Database → TF-IDF → Logistic Regression → Theme Prediction → Validation → Database → Dashboard**

The model will be part of the actual Django application instead of only running as a separate Python script. Users will eventually be able to start the analysis through the website.

## Initial Experimentation

I created an initial prototype using TF-IDF and Logistic Regression. The first version was trained using 20 synthetic cancellation responses across four themes. It correctly classified three out of four test responses but the confidence scores were low.

I then created a larger dataset with 80 labeled training responses and 32 separate test responses. The initial model achieved 84.4% accuracy with a macro F1 score of 0.841. It correctly classified 27 out of 32 responses.

After reviewing the incorrect predictions I added 12 more training examples to improve how the model recognized different wording. I then retrained the model using 92 examples.

The updated model achieved 90.6% accuracy with a macro F1 score of 0.905. It correctly classified 29 out of 32 responses. The prediction time for all 32 responses was approximately 0.002 seconds.

The improvement showed that adding more varied training examples helped the model recognize cancellation reasons. However, both tests used synthetic data and the same test set was used after reviewing its mistakes. This means the results show improvement on the development dataset but do not establish how accurate the model will be on real customer feedback.

## Technical Feasibility

I saved the trained TF-IDF and Logistic Regression pipeline as `cancellation_logistic.joblib`. The updated model file is approximately 44.9 KB. It can be loaded again without retraining which makes it more practical for Django integration.

The model does not require a GPU or an external AI service. It can make predictions using Scikit-learn on a CPU. This should make it easier to maintain and deploy than a larger pretrained model.

PythonAnywhere's free plan has a 512 MiB disk storage limit. Although the model file is small we still need to check whether the complete Django application and its dependencies fit within the available storage.

## AI Reliability and Limitations

The model can still make incorrect predictions when customers use unfamiliar wording or mention multiple reasons for canceling. Logistic Regression also predicts one main theme which may not fully represent feedback containing several complaints.

I plan to use a confidence threshold so uncertain predictions can be reviewed manually. The application will also need to check for empty responses and handle missing model files or unexpected errors without crashing.

Customer feedback may contain personal information so the analysis should only be available to authorized users. Since the model runs locally it will not need to send the feedback to an external AI provider.

The current training dataset is limited because most responses are written clearly and follow similar patterns. Real customer feedback may contain spelling mistakes or incomplete sentences. Customers may also mention multiple reasons for canceling. I plan to create a more realistic test dataset with different writing styles to see how well the model handles feedback it has not seen before.

## Remaining Work

The next step is to connect the saved model to Django using `responses_for_analysis()` and `apply_theme_assignments()`. This will allow Undone to automatically classify customer feedback and store the results in the database.

I also need to add error handling and make the AI analysis available through the website. Once that is working I will test the complete workflow using uploaded customer feedback.

For the final evaluation I will run at least five realistic tests and record the actual outputs and latency. I will also document two genuine failure cases and an improvement based on the results. I plan to use a new independent test set to evaluate the model because the current test responses were already used during development.
