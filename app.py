import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

load_dotenv()

from helpers import (
    analyze_generic_phrases,
    analyze_stylometric,
    combine_scores,
    clamp_score,
    classify_with_llm,
    find_existing_appeal,
    find_latest_classification_entry,
    generate_label,
    now_iso,
    read_audit_log,
    score_to_attribution,
    write_audit_entry,
)

app = Flask(__name__)

# Initialize Flask-Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"  # Use in-memory storage for rate limiting
)


@app.route("/appeal", methods=["POST"])
def appeal():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    content_id = data.get("content_id")
    creator_id = data.get("creator_id")
    creator_reasoning = data.get("creator_reasoning")

    if not (content_id and creator_reasoning and creator_id):
        return jsonify({"error": "content_id, creator_id, and creator_reasoning are required."}), 400

    original_entry = find_latest_classification_entry(content_id)

    if not original_entry:
        return jsonify({"error": f"No classification found for this content_id: {content_id}"}), 404

    if original_entry.get("creator_id") != creator_id:
        return jsonify({
            "error": "Only the original creator can appeal this classification."
        }), 403

    existing_appeal = find_existing_appeal(content_id, creator_id)

    if existing_appeal:
        return jsonify({
            "error": "An appeal has already been submitted for this content.",
            "content_id": content_id,
            "status": "under_review"
        }), 409

    appeal_entry = {
        "timestamp": now_iso(),
        "event_type": "appeal",
        "content_id": content_id,
        "creator_id": creator_id,
        "original_attribution": original_entry.get("attribution"),
        "original_confidence": original_entry.get("confidence"),
        "signals": original_entry.get("signals", {}),
        "label": original_entry.get("label"),
        "status": "under_review",
        "creator_reasoning": creator_reasoning,
    }

    write_audit_entry(appeal_entry)

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "status": "under_review",
        "message": "Appeal received and marked for review.",
    }), 200


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
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
    llm_score = clamp_score(llm_result.get("llm_score", 0.5))

    stylometric_result = analyze_stylometric(text)
    stylometric_score = clamp_score(stylometric_result.get("stylometric_score", 0.5))

    generic_phrase_result = analyze_generic_phrases(text)
    generic_phrase_score = clamp_score(generic_phrase_result.get("generic_phrase_score", 0.0))

    confidence = combine_scores(llm_score, stylometric_score, generic_phrase_score)
    attribution = score_to_attribution(confidence)

    response = {
        "content_id": content_id,
        "creator_id": creator_id,
        "attribution": attribution,
        "confidence": confidence,
        "signals": {
            "llm_score": llm_score,
            "stylometric_score": stylometric_score,
            "generic_phrase_score": generic_phrase_score
        },
        "stylometric_metrics": stylometric_result.get("metrics", {}),
        "generic_phrase_matches": generic_phrase_result.get("matched_phrases", []),
        "label": generate_label(attribution),
        "status": "classified"
    }

    audit_entry = {
        "timestamp": now_iso(),
        "event_type": "classification",
        **response,
        "llm_reasoning": llm_result.get("reasoning", "")
    }

    write_audit_entry(audit_entry)

    return jsonify(response), 200


@app.route("/log", methods=["GET"])
def audit_log():
    return jsonify({"entries": read_audit_log()}), 200


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({
        "error": error.name,
        "message": error.description
    }), error.code


@app.errorhandler(Exception)
def handle_server_error(error):
    return jsonify({
        "error": "Internal Server Error",
        "message": "Something went wrong while processing the request."
    }), 500


if __name__ == "__main__":
    app.run(debug=True)
