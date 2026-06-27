import json
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from groq import Groq

load_dotenv()

app = Flask(__name__)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

AUDIT_LOG_FILE = "audit_log.json"


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


def classify_with_llm(text: str) -> dict:
    prompt = f"""
You are helping classify whether a piece of text is likely AI-generated or human-written.

Return only JSON with this format:
{{
"attribution": "likely_ai" or "likely_human" or "uncertain",
"llm_score": a number from 0.0 to 1.0,
"reasoning": "brief explanation"
}}

Score meaning:
0.0 = strongly human-written
0.5 = uncertain or mixed evidence
1.0 = strongly AI-generated

Text:
{text}
"""

    response = client.chat.completions.create(
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
            "attribution": "uncertain",
            "llm_score": 0.5,
            "reasoning": "The LLM response could not be parsed as JSON."
        }

    return result


def normalize_attribution(value: str) -> str:
    allowed = {"likely_ai", "likely_human", "uncertain"}

    if value in allowed:
        return value

    return "uncertain"


@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    creator_id = data.get("creator_id")
    text = data.get("text")

    if not creator_id or not text:
        return jsonify({"error": "creator_id and text are required."}), 400

    content_id = str(uuid.uuid4())

    llm_result = classify_with_llm(text)

    attribution = normalize_attribution(llm_result.get("attribution", "uncertain"))
    llm_score = float(llm_result.get("llm_score", 0.5))

    response = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": llm_score,
        "signals": {
            "llm_score": llm_score,
            "stylometric_score": None
        },
        "label": "Placeholder label for Milestone 3.",
        "status": "classified"
    }

    audit_entry = {
        "timestamp": now_iso(),
        **response,
        "llm_reasoning": llm_result.get("reasoning", "")
    }

    write_audit_entry(audit_entry)

    return jsonify(response), 200


@app.route("/log", methods=["GET"])
def audit_log():
    return jsonify({"entries": read_audit_log()}), 200


if __name__ == "__main__":
    app.run(debug=True)
