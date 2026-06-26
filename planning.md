# Provenance Guard Planning

## Milestone 1 Notes

### System Goal
Provenance Guard analyzes text submitted to a creative platform and returns an attribution result, confidence score, and transparency label. It also keeps an audit log and allows creators to appeal a classification.

### Submission Flow
1. A creator sends text and creator_id to POST /submit.
2. The API validates the request.
3. Signal 1 analyzes the text using an LLM-based classifier.
4. Signal 2 analyzes the text using stylometric heuristics.
5. The confidence scorer combines both signal scores.
6. The label generator chooses one of three transparency labels:
   - likely AI-generated
   - uncertain
   - likely human-written
7. The system saves a structured audit log entry.
8. The API returns JSON with content_id, attribution, confidence, signal scores, label text, and status.

### Appeal Flow
1. A creator sends content_id and creator_reasoning to POST /appeal.
2. The system finds the original classification.
3. The content status changes to under_review.
4. The appeal reasoning is added to the audit log.
5. The API returns confirmation that the appeal was received.

### Signal 1: LLM-based Classifier
* Measures: overal semantic and stylistic impression of whether the text is likely AI-generated or human-written.
* Why useful: an LLM can judge coherence, tone, repetitiveness, and other high-level features that may indicate AI generation.
* Blind spot: it may over-trust certain stylistic features that are common in both AI and human writing, leading to false positives or negatives.

### Signal 2: Stylometric Heuristics
* Measures: low-level features such as word frequency, sentence length, punctuation usage, and other statistical patterns.
* Why useful: these features can reveal subtle differences in writing style that are difficult for humans to detect, and they are less likely to be influenced by the content's topic or meaning.
* Blind spot: stylometric features can be manipulated by a skilled human writer, and they may not capture the overall semantic coherence of the text, leading to misclassification.

### False positive scenario
A human creator submits a polished formal essay. The LLM signal may score it as AI-like because the tone is structured and balanced. The stylometric signal may also score it as AI-like if the sentence lengths are uniform and vocabulary is formal.

To reduce harm, the system should avoid using harsh wording unless confidence is very high. Borderline scores should produce an uncertain label instead of accusing the creator of using AI. The creator can submit an appeal with reasoning, and the content status changes to under_review.

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
