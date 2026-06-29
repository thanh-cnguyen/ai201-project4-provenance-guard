import json
import os
import re
from datetime import datetime, timezone

from groq import Groq


AUDIT_LOG_FILE = "audit_log.json"

LABEL_MAPPING = {
    "likely_ai": "This submission appears likely to be AI-generated based on multiple analysis signals. This label is not a final judgment and may be appealed by the creator.",
    "uncertain": "This submission has mixed signals, so we cannot confidently determine whether it was AI-generated or human-written.",
    "likely_human": "This submission appears likely to be human-written based on the available analysis signals."
}


GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing. Add it to your .env file.")

_client = Groq(api_key=GROQ_API_KEY)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_audit_log_exists():
    if not os.path.exists(AUDIT_LOG_FILE):
        with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as file:
            json.dump([], file)


def read_audit_log() -> list:
    ensure_audit_log_exists()

    try:
        with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        return []


def write_audit_entry(entry: dict):
    entries = read_audit_log()
    entries.append(entry)

    with open(AUDIT_LOG_FILE, "w", encoding="utf-8") as file:
        json.dump(entries, file, indent=2)


def clamp_score(score: float, default: float = 0.5) -> float:
    try:
        score = float(score)
    except (ValueError, TypeError):
        score = default

    return max(0.0, min(1.0, score))


def round_score(score: float) -> float:
    return round(clamp_score(score), 2)


def round_metric(value: float) -> float:
    try:
        return round(float(value), 2)
    except (ValueError, TypeError):
        return 0.0


def classify_with_llm(text: str) -> dict:
    prompt = f"""
You are helping classify whether a piece of text is likely AI-generated or human-written based on semantic and stylistic cues.

Return only JSON with this format:
{{"llm_score": a number from 0.0 to 1.0, "reasoning": "brief explanation"}}

Score meaning:
0.0 = strongly human-written
0.5 = uncertain or mixed evidence
1.0 = strongly AI-generated

Important: 
- You are not making the final system decision.
- Your score will be combined with a separate stylometric heuristic score.
- Avoid overconfidence when the text is short, generic, or could plausibly be human-written.

Text:
{text}
"""

    response = _client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.1,
    )

    content = response.choices[0].message.content

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {
            "llm_score": 0.5,
            "reasoning": "The LLM response could not be parsed as JSON."
        }
    except Exception as e:
        result = {
            "llm_score": 0.5,
            "reasoning": f"An unexpected error occurred while parsing the LLM response: {str(e)}"
        }

    return result


def analyze_stylometric(text: str) -> dict:
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]

    words = re.findall(r'\b\w+\b', text.lower())

    if not words or not sentences:
        return {
            "stylometric_score": 0.5,
            "metrics": {
                "average_sentence_length": 0,
                "sentence_length_variance": 0,
                "type_token_ratio": 0,
                "punctuation_density": 0,
            }
        }

    sentence_lengths = [len(re.findall(r'\b\w+\b', s)) for s in sentences]
    average_sentence_length = sum(sentence_lengths) / len(sentence_lengths)

    sentence_length_variance = sum((l - average_sentence_length) ** 2 for l in sentence_lengths) / len(sentence_lengths)

    unique_words = set(words)
    type_token_ratio = len(unique_words) / len(words)

    punctuation_count = len(re.findall(r'[^\w\s]', text))
    punctuation_density = punctuation_count / max(len(words), 1)

    # AI-like writing often has lower sentence variation and moderate vocabulary diversity.
    uniformity_score = 1.0 - min(sentence_length_variance / 50, 1.0)

    # Very low diversity can suggest repetitive/generated text.
    low_diversity_score = 1.0 - min(type_token_ratio / 0.75, 1.0)

    # Very low or very even punctuation can suggest polished/generated text.
    punctuation_score = 1.0 - min(punctuation_density / 0.25, 1.0)

    stylometric_score = uniformity_score * 0.50 + low_diversity_score * 0.30 + punctuation_score * 0.20

    return {
        "stylometric_score": round_score(stylometric_score),
        "metrics": {
            "average_sentence_length": round_metric(average_sentence_length),
            "sentence_length_variance": round_metric(sentence_length_variance),
            "type_token_ratio": round_metric(type_token_ratio),
            "punctuation_density": round_metric(punctuation_density),
        },
    }


def find_latest_classification_entry(content_id: str):
    entries = read_audit_log()

    for entry in reversed(entries):
        if (
            entry.get("content_id") == content_id
            and entry.get("event_type") == "classification"
        ):
            return entry

    return None


def find_existing_appeal(content_id: str, creator_id: str):
    entries = read_audit_log()

    for entry in reversed(entries):
        if (
            entry.get("content_id") == content_id
            and entry.get("creator_id") == creator_id
            and entry.get("event_type") == "appeal"
        ):
            return entry

    return None


def score_to_attribution(score: float) -> str:
    if score < 0.4:
        return "likely_human"
    if score >= 0.75:
        return "likely_ai"
    return "uncertain"


def generate_label(attribution: str) -> str:
    return LABEL_MAPPING.get(attribution, LABEL_MAPPING["uncertain"])


def combine_scores(llm_score: float, stylometric_score: float) -> float:
    combined_score = (llm_score * 0.60) + (stylometric_score * 0.40)
    return round_score(combined_score)
