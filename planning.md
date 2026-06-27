# Provenance Guard Planning

---

## System Goal
Provenance Guard analyzes text submitted to a creative platform and returns an attribution result, confidence score, and transparency label. It also keeps an audit log and allows creators to appeal a classification.

---

## Architecture

### Submission Flow

Client / Creator
   |
   | POST /submit
   | { creator_id, text }
   v
Flask API
   |
   | raw text
   v
Request Validator
   |
   | validated text
   v
Detection Pipeline
   |
   |----------------------------|
   v                            v
Signal 1: Groq LLM        Signal 2: Stylometric Heuristics
   |                            |
   | llm_score                  | stylometric_score
   |----------------------------|
                  |
                  v
          Confidence Scorer
                  |
                  | combined confidence + attribution
                  v
          Transparency Label Generator
                  |
                  | label text
                  v
              Audit Log
                  |
                  | structured decision entry
                  v
              JSON Response


### Appeal Flow

Client / Creator
   |
   | POST /appeal
   | { content_id, creator_reasoning }
   v
Flask API
   |
   | lookup content_id
   v
Content Status Store
   |
   | status = under_review
   v
Audit Log
   |
   | appeal entry + original decision reference
   v
JSON Response

### API Surface

#### POST /submit
* Input:
    ```
    {
        "creator_id": "user-123",
        "text": "Submitted creative text here"
    }
    ```
* Output:
    ```
    {
        "content_id": "uuid",
        "creator_id": "user-123",
        "attribution": "likely_ai | uncertain | likely_human",
        "confidence": 0.82,
        "signals": {
            "llm_score": 0.86,
            "stylometric_score": 0.77
        },
        "label": "Plain-language transparency label shown to readers.",
        "status": "classified"
    }
    ```

#### POST /appeal
* Input:
    ```
    {
        "content_id": "uuid",
        "creator_reasoning": "I wrote this myself and can provide drafts."
    }
    ```

* Output:
    ```
    {
        "content_id": "uuid",
        "status": "under_review",
        "message": "Appeal received and marked for review."
    }
    ```

#### GET /log
* Output:
    ```
    [
        {
            "content_id": "uuid",
            "creator_id": "user-123",
            "attribution": "likely_ai | uncertain | likely_human",
            "confidence": 0.82,
            "signals": {
                "llm_score": 0.86,
                "stylometric_score": 0.77
            },
            "label": "Plain-language transparency label shown to readers.",
            "status": "classified",
            "timestamp": "2024-06-01T12:34:56Z"
        },
        ...
    ]
    ```

---

## Detection Signals

### Signal 1: LLM-based Classifier
* Measures: overall semantic and stylistic impression of whether the text is likely AI-generated or human-written.
* Why useful: an LLM can judge coherence, tone, repetitiveness, and other high-level features that may indicate AI generation.
* Blind spot: it may over-trust certain stylistic features that are common in both AI and human writing, leading to false positives or negatives.

### Signal 2: Stylometric Heuristics
* Measures: low-level features such as word frequency, sentence length, punctuation usage, and other statistical patterns.
* Why useful: these features can reveal subtle differences in writing style that are difficult for humans to detect, and they are less likely to be influenced by the content's topic or meaning.
* Blind spot: stylometric features can be manipulated by a skilled human writer, and they may not capture the overall semantic coherence of the text, leading to misclassification.

---

## Uncertainty Representation

Each detection signal returns a score from 0.0 to 1.0, where:

- 0.0 means strongly human-written
- 0.5 means uncertain or mixed evidence
- 1.0 means strongly AI-generated

The final confidence score is a weighted combination of both signals:

```python
combined_score = (llm_score * 0.60) + (stylometric_score * 0.40)
```

The system maps the combined score into three attribution categories:

| Combined Score Range | Attribution  | Label Type            |
|----------------------|--------------|-----------------------|
| 0.75–1.00            | likely_ai    | High-confidence AI    |
| 0.40–0.74            | uncertain    | Uncertain             |
| 0.00–0.39            | likely_human | High-confidence human |

A score around 0.50 means the system has mixed evidence and should avoid making a strong attribution claim. Because falsely labeling human writing as AI-generated can harm creators, the system only uses the high-confidence AI label when the combined score is at least 0.75.

---

## Transparency Label Design

The transparency label should be understandable to a non-technical reader. It should explain the result without sounding like an accusation.

| Result Type | Exact Label Text |
|---|---|
| High-confidence AI | "This submission appears likely to be AI-generated based on multiple analysis signals. This label is not a final judgment and may be appealed by the creator." |
| Uncertain | "This submission has mixed signals, so we cannot confidently determine whether it was AI-generated or human-written." |
| High-confidence human | "This submission appears likely to be human-written based on the available analysis signals." |

---

## Appeals Workflow

A creator can submit an appeal if they believe their content was misclassified.

The appeal endpoint accepts:

```json
{
  "content_id": "generated-content-id",
  "creator_reasoning": "I wrote this myself and can provide drafts or revision history."
}
```

When an appeal is received, the system:

1. Looks up the original content_id.
2. Stores the creator's reasoning.
3. Updates the content status from classified to under_review.
4. Writes a structured appeal entry to the audit log.
5. Returns a confirmation response.

A human reviewer would need to see the original text, attribution result, confidence score, individual signal scores, transparency label, creator reasoning, timestamp, and current status.

---

## Anticipated Edge Cases

### Edge Case 1: Formal human writing
A polished essay, academic paragraph, or professional blog post may have consistent sentence structure and formal vocabulary. The LLM signal and stylometric signal may both interpret this as AI-like, even if it was written by a human. This could create a false positive, so borderline scores should map to the uncertain label instead of likely_ai.

### Edge Case 2: Short creative text
A very short poem, quote, caption, or micro-story may not contain enough text for reliable stylometric analysis. Sentence length variance, vocabulary diversity, and punctuation density are less meaningful when the sample is too small. The system should treat very short submissions as lower-confidence cases.

### Edge Case 3: Edited AI text
A creator may heavily edit AI-generated text to make it more personal and irregular. The stylometric signal may score it as more human-like, while the LLM signal may still detect generic phrasing. This disagreement should push the combined score toward uncertain instead of overconfidently labeling it.

---

## AI Tool Plan

### Milestone 3: Submission Endpoint + First Signal
I will provide the AI tool with the Architecture section, API Surface section, and Signal 1 description. I will ask it to generate a Flask app skeleton, a POST /submit route, and a Groq-based LLM classification function.

I will verify the output by testing the route with curl first using a hardcoded response, then testing the LLM signal independently before wiring it into the endpoint.

### Milestone 4: Second Signal + Confidence Scoring
I will provide the AI tool with the Detection Signals section, Uncertainty Representation section, and Architecture diagram. I will ask it to generate the stylometric heuristic function and the scoring function that combines the LLM score and stylometric score.

I will verify the output by testing at least four inputs: clearly AI-generated text, clearly human-written text, formal human writing, and lightly edited AI-style text. I will check that the scores vary meaningfully and that all three label categories are reachable.

### Milestone 5: Production Layer
I will provide the AI tool with the Transparency Label Design section, Appeals Workflow section, API Surface section, and Architecture diagram. I will ask it to generate the label generation function, POST /appeal endpoint, rate limiting setup, and audit log updates.

I will verify the output by testing that all three label variants can appear, an appeal changes status to under_review, the appeal appears in the audit log, and the rate limit returns a 429 response when exceeded.
