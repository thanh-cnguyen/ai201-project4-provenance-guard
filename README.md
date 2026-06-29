# Provenance Guard

Provenance Guard is a Flask backend system for analyzing text submitted to a creative platform and estimating whether the content is likely AI-generated, likely human-written, or uncertain.

The system uses a multi-signal detection pipeline, returns a confidence score, generates a reader-facing transparency label, supports creator appeals, applies rate limiting, and stores structured audit logs.

---

## Overview

Creative platforms need a way to give readers more context about submitted work without unfairly accusing creators. Provenance Guard is designed as a backend service that could be connected to a writing, blogging, or creative-sharing platform.

A creator submits text to the API. The system analyzes the text using two independent signals:

1. An LLM-based semantic/style signal.
2. A stylometric heuristic signal.

The system combines both signal scores into one confidence score, maps that score to an attribution result, returns a plain-language transparency label, and stores the decision in an audit log.

---

## Architecture Overview

### Submission Flow

```text
POST /submit
→ validate creator_id and text
→ run LLM-based signal
→ run stylometric heuristic signal
→ combine signal scores
→ determine attribution
→ generate transparency label
→ write classification entry to audit log
→ return structured JSON response
```

### Appeal Flow

```text
POST /appeal
→ validate content_id, creator_id, and creator_reasoning
→ find original classification entry
→ verify the creator_id matches the original creator
→ check whether an appeal already exists
→ write appeal entry to audit log
→ return under_review status
```

---

## API Endpoints

### POST `/submit`

Accepts a text submission for attribution analysis.

Example request:

```json
{
  "creator_id": "user-123",
  "text": "The sun dipped below the horizon, painting the sky in quiet shades of amber and violet."
}
```

Example response:

```json
{
  "attribution": "likely_human",
  "confidence": 0.36,
  "content_id": "fa0bcd0a-6ff5-4b07-a991-6f3e6d9972a1",
  "creator_id": "user-123",
  "label": "This submission appears likely to be human-written based on the available analysis signals.",
  "signals": {
    "llm_score": 0.2,
    "stylometric_score": 0.6,
    "generic_phrase_score": 0.25
  },
  "status": "classified",
  "stylometric_metrics": {
    "average_sentence_length": 16.0,
    "punctuation_density": 0.12,
    "sentence_length_variance": 0.0,
    "type_token_ratio": 0.88
  }
}
```

### POST `/appeal`

Allows a creator to appeal a classification.

Example request:

```json
{
  "content_id": "fa0bcd0a-6ff5-4b07-a991-6f3e6d9972a1",
  "creator_id": "user-123",
  "creator_reasoning": "I wrote this myself and can provide drafts or revision history."
}
```

Example response:

```json
{
  "content_id": "fa0bcd0a-6ff5-4b07-a991-6f3e6d9972a1",
  "creator_id": "user-123",
  "message": "Appeal submitted successfully.",
  "status": "under_review"
}
```

### GET `/log`

Returns structured audit log entries.

---

## Detection Signals

### Signal 1: LLM-Based Classifier

The LLM signal measures semantic and stylistic cues in the submitted text. It looks at tone, coherence, repetitiveness, generic phrasing, and whether the text appears naturally human-written or AI-generated.

The LLM returns:

```json
{
  "llm_score": 0.2,
  "reasoning": "Brief explanation for the score."
}
```

The LLM does not make the final attribution decision by itself. It only contributes one score to the larger pipeline.

**What it captures:** semantic coherence, tone, phrasing, and high-level writing style.

**What it misses:** polished human writing may look AI-like, and edited AI writing may look more human. It can also be unreliable on very short text.

### Signal 2: Stylometric Heuristics

The stylometric signal measures structural writing patterns using pure Python calculations.

Metrics used:

* average sentence length
* sentence length variance
* type-token ratio
* punctuation density

The stylometric signal returns a score from `0.0` to `1.0`.

**What it captures:** sentence uniformity, vocabulary diversity, punctuation usage, and structural writing patterns.

**What it misses:** short texts do not provide enough data for reliable stylometric analysis. Poetry, casual writing, or intentionally simple writing may also be misread.

### Signal 3: Generic AI Phrase Heuristic

The generic AI phrase heuristic looks for boilerplate phrases and wording patterns that often appear in AI-generated text, such as "it is important to note," "as an AI language model," "let's dive in," or "comprehensive guide." It counts how many phrases from a curated list appear in the submission and converts that count into a `generic_phrase_score` from 0.0 to 1.0.

**What it captures:** repeated AI-like boilerplate phrasing, generic transitions, and polished reusable wording patterns.

**What it misses:** the phrase list is not exhaustive, so AI-generated text may avoid these phrases completely. Human writers can also naturally use formal or common phrases from the list. Because this signal can miss edited AI text and create false positives, it is weighted lower than the LLM and stylometric signals.

---

## Confidence Scoring

Each signal returns a score from `0.0` to `1.0`:

* `0.0` = strongly human-written
* `0.5` = uncertain or mixed evidence
* `1.0` = strongly AI-generated

The final confidence score is calculated using a weighted average:

```python
combined_score = (llm_score * 0.50) + (stylometric_score * 0.30) + (generic_phrase_score * 0.20)
```

I weighted the LLM signal slightly higher because it can evaluate semantic and stylistic context. The stylometric signal still matters because it provides a separate structural check.

The final attribution is based on the combined score:

| Combined Score Range | Attribution    | Label Type            |
| -------------------- | -------------- | --------------------- |
| 0.75–1.00            | `likely_ai`    | High-confidence AI    |
| 0.40–0.74            | `uncertain`    | Uncertain             |
| 0.00–0.39            | `likely_human` | High-confidence human |

A score near `0.50` means the system has mixed evidence. Because falsely labeling human writing as AI-generated can harm creators, the system only returns `likely_ai` when the combined score is at least `0.75`.

### Example Score 1: Lower AI-Likelihood / Likely Human

Input:

```text
The sun dipped below the horizon, painting the sky in quiet shades of amber and violet.
```

Output:

```json
{
  "attribution": "likely_human",
  "confidence": 0.36,
  "signals": {
    "llm_score": 0.2,
    "stylometric_score": 0.6,
    "generic_phrase_score": 0.25
  }
}
```

This was classified as `likely_human` because the combined score was below `0.40`.

### Example Score 2: Rate Limit Test Submission

Input:

```text
This is a test submission for rate limit testing purposes only.
```

Output:

```json
{
  "attribution": "likely_human",
  "confidence": 0.25,
  "signals": {
    "llm_score": 0.0,
    "stylometric_score": 0.63,
    "generic_phrase_score": 0.25
  }
}
```

This was also classified as `likely_human`, but with a different confidence score. The score difference shows that the system is not returning a constant value.

---

## Transparency Labels

The system returns a plain-language label that could be shown to readers on a creative platform.

| Result Type           | Exact Label Text                                                                                                                                               |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| High-confidence AI    | "This submission appears likely to be AI-generated based on multiple analysis signals. This label is not a final judgment and may be appealed by the creator." |
| Uncertain             | "This submission has mixed signals, so we cannot confidently determine whether it was AI-generated or human-written."                                          |
| High-confidence human | "This submission appears likely to be human-written based on the available analysis signals."                                                                  |

These labels avoid technical language and avoid presenting the classification as a final judgment.

---

## Appeals Workflow

Creators can appeal a classification by submitting:

* `content_id`
* `creator_id`
* `creator_reasoning`

When an appeal is submitted, the system:

1. Looks up the original classification.
2. Verifies that the appealing creator matches the original `creator_id`.
3. Checks whether an appeal already exists.
4. Logs the appeal with the original attribution and confidence.
5. Returns `status: under_review`.

The system does not automatically reclassify appealed content. Instead, it marks the content for human review.

### Appeal Example

```json
{
  "content_id": "fa0bcd0a-6ff5-4b07-a991-6f3e6d9972a1",
  "creator_id": "user-123",
  "creator_reasoning": "I wrote this myself and can provide drafts or revision history.",
  "event_type": "appeal",
  "original_attribution": "likely_human",
  "original_confidence": 0.36,
  "status": "under_review"
}
```

The system also prevents duplicate appeals for the same `content_id` and `creator_id`.

---

## Rate Limiting

The `/submit` endpoint uses Flask-Limiter with these limits:

```text
10 per minute; 100 per day
```

I chose `10 per minute` to prevent rapid automated abuse or flooding. I chose `100 per day` because a normal creator may submit multiple drafts or pieces of writing in one day, but they are unlikely to need hundreds of submissions.

When the limit is exceeded, the API returns `429 Too Many Requests`.

Rate limit test output:

```text
200
200
200
200
200
200
200
200
200
200
429
429
```

---

## Audit Log Evidence

The audit log stores structured JSON entries for both classification decisions and appeals.

Classification entries include:

* timestamp
* event type
* content ID
* creator ID
* attribution
* confidence
* individual signal scores
* transparency label
* status

Appeal entries include:

* timestamp
* event type
* content ID
* creator ID
* creator reasoning
* original attribution
* original confidence
* status

Example audit log output:

```json
{
  "entries": [
    {
      "attribution": "likely_human",
      "confidence": 0.36,
      "content_id": "fa0bcd0a-6ff5-4b07-a991-6f3e6d9972a1",
      "creator_id": "user-123",
      "event_type": "classification",
      "label": "This submission appears likely to be human-written based on the available analysis signals.",
      "signals": {
        "llm_score": 0.2,
        "stylometric_score": 0.6,
        "generic_phrase_score": 0.25
      },
      "status": "classified",
      "timestamp": "2026-06-28T17:59:58.165944+00:00"
    },
    {
      "content_id": "fa0bcd0a-6ff5-4b07-a991-6f3e6d9972a1",
      "creator_id": "user-123",
      "creator_reasoning": "I wrote this myself and can provide drafts or revision history.",
      "event_type": "appeal",
      "original_attribution": "likely_human",
      "original_confidence": 0.36,
      "signals": {
        "llm_score": 0.2,
        "stylometric_score": 0.6
      },
      "status": "under_review",
      "timestamp": "2026-06-28T18:00:08.931037+00:00"
    },
    {
      "attribution": "likely_human",
      "confidence": 0.25,
      "content_id": "2030272f-8da0-4933-8729-131acd395a23",
      "creator_id": "rate-test-user",
      "event_type": "classification",
      "label": "This submission appears likely to be human-written based on the available analysis signals.",
      "signals": {
        "llm_score": 0.0,
        "stylometric_score": 0.63
      },
      "status": "classified",
      "timestamp": "2026-06-28T18:00:10.079041+00:00"
    }
  ]
}
```

---

## Known Limitations

### Short text can be unreliable

Very short text does not provide enough evidence for stylometric analysis. For example, a single sentence may have zero sentence length variance simply because there is only one sentence. This can make the stylometric score less meaningful.

### Polished human writing can look AI-like

Formal essays, academic writing, and professional blog posts may have consistent sentence structure and balanced vocabulary. Both the LLM and stylometric signal may interpret this as AI-like even when it was written by a human.

### Edited AI text can look human

If AI-generated text is heavily edited by a person, the stylometric signal may become more human-like. This can push the result toward uncertain or likely human.

---

## Spec Reflection

One way the spec helped guide my implementation was by forcing me to define the system flow before writing code. Because I had already planned the `/submit` flow, detection signals, confidence thresholds, label variants, and appeal flow, it was easier to implement the backend in milestones instead of trying to build everything at once.

One way my implementation diverged from the original plan was the LLM signal output. At first, I planned for the LLM to return both an attribution and a score. During implementation, I changed it so the LLM returns only `llm_score` and reasoning. This made the design cleaner because the final attribution now comes from the combined multi-signal score instead of the LLM alone.

---

## AI Usage

### Instance 1: Planning the architecture and API surface

I used AI to help turn the project requirements into a concrete architecture plan. I asked for help defining the submission flow, appeal flow, API endpoints, and detection signals. The AI helped produce an initial structure for `planning.md`, but I revised it to match my own implementation choices, including the `/log` endpoint, creator ownership check for appeals, and the exact confidence thresholds.

### Instance 2: Implementing the multi-signal scoring pipeline

I used AI to help design the stylometric heuristic function and the combined scoring logic. The AI suggested using sentence length variance, vocabulary diversity, and punctuation density. I revised the implementation so the LLM returns only `llm_score` and reasoning, while the final attribution is determined by the combined score.

### Instance 3: Debugging API testing and error handling

I used AI to help debug Windows CMD curl formatting, JSON request parsing, and rate-limit behavior. I adjusted the curl commands for Windows Command Prompt and added JSON error handling so rate limiting correctly returns `429 Too Many Requests` instead of a generic server error.

---

## How to Run

### 1. Create a virtual environment

```bash
python -m venv .venv
```

### 2. Activate the virtual environment

Windows Command Prompt:

```cmd
.venv\Scripts\activate
```

Git Bash:

```bash
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Create a `.env` file in the project root:

```text
GROQ_API_KEY=your_key_here
LLM_MODEL=llama-3.3-70b-versatile
```

### 5. Run the app

```bash
python app.py
```

The app runs at:

```text
http://localhost:5000
```

---

## Demo Commands

### Submit Content

Windows Command Prompt:

```cmd
curl -s -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\":\"user-123\",\"text\":\"The sun dipped below the horizon, painting the sky in quiet shades of amber and violet.\"}"
```

### View Audit Log

```cmd
curl -s -X GET http://localhost:5000/log
```

### Submit Appeal

Replace the content ID with one returned from `/submit`.

```cmd
curl -s -X POST http://localhost:5000/appeal -H "Content-Type: application/json" -d "{\"content_id\":\"PASTE_CONTENT_ID_HERE\",\"creator_id\":\"user-123\",\"creator_reasoning\":\"I wrote this myself and can provide drafts or revision history.\"}"
```

### Rate Limit Test

```cmd
for /L %i in (1,1,12) do curl -s -o NUL -w "%{http_code}\n" -X POST http://localhost:5000/submit -H "Content-Type: application/json" -d "{\"creator_id\":\"rate-test-user\",\"text\":\"This is a test submission for rate limit testing purposes only.\"}"
```

## Stretch Feature: Ensemble Detection

I implemented the ensemble detection stretch feature by adding a third signal: a generic AI phrase heuristic.

The final system now uses three distinct signals:

1. `llm_score`
2. `stylometric_score`
3. `generic_phrase_score`

The combined score is calculated as:

```python
combined_score = (
    llm_score * 0.50
    + stylometric_score * 0.30
    + generic_phrase_score * 0.20
)
```
