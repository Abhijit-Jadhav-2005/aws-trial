
import re
import logging
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_from_directory,
    abort,
)

# --------------------------------------------------
# Flask application configuration
# --------------------------------------------------

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
PDF_FOLDER = (BASE_DIR / "pdfs").resolve()

# Create the PDF folder automatically if it doesn't exist.
PDF_FOLDER.mkdir(parents=True, exist_ok=True)

# Limit incoming request size.
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB

logging.basicConfig(level=logging.INFO)


# --------------------------------------------------
# Get available PDF files
# --------------------------------------------------

def get_pdf_files():
    """Return PDF filenames stored directly in the pdfs folder."""

    files = []

    for path in PDF_FOLDER.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() != ".pdf":
            continue

        # Ignore files whose resolved parent is outside the PDF folder.
        if path.resolve().parent != PDF_FOLDER:
            continue

        files.append(path.name)

    return sorted(files, key=str.lower)


# --------------------------------------------------
# Normalize words for filename matching
# --------------------------------------------------

STOP_WORDS = {
    "find", "send", "give", "get", "want", "need",
    "me", "my", "the", "a", "an", "please", "show",
    "share", "download", "pdf", "file", "document",
    "notes", "note", "of", "for", "on", "about",
    "i", "can", "you", "could", "would", "some",
    "to", "from", "provide", "fetch", "search",
    "looking", "lookingfor", "material", "study",
    "materials", "book", "books"
}


def normalize_words(text):
    """Convert text into meaningful lowercase words."""

    words = set(re.findall(r"[a-z0-9]+", text.lower()))

    return words - STOP_WORDS


# --------------------------------------------------
# Match a user's request to a PDF
# --------------------------------------------------

def match_pdf(user_message):
    """
    Find the best matching PDF using its filename.
    This function does not call Gemini, so it avoids
    network delays for ordinary PDF searches.
    """

    files = get_pdf_files()

    if not files:
        return None

    query_words = normalize_words(user_message)

    if not query_words:
        return None

    best_file = None
    best_score = 0.0

    for filename in files:
        filename_words = normalize_words(
            Path(filename).stem
        )

        if not filename_words:
            continue

        # Prefer a complete filename match.
        if filename_words.issubset(query_words):
            score = (
                len(filename_words) / len(query_words)
            )

            if score > best_score:
                best_score = score
                best_file = filename

        # Also support a request that contains most of
        # the filename words, without accepting weak matches.
        else:
            matched_words = filename_words & query_words

            if matched_words:
                score = (
                    len(matched_words) / len(filename_words)
                )

                if score >= 0.75 and score > best_score:
                    best_score = score
                    best_file = filename

    # Reject weak or unrelated matches.
    if best_file and best_score >= 0.4:
        return best_file

    return None


# --------------------------------------------------
# Homepage
# --------------------------------------------------

@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")


# --------------------------------------------------
# Chat API
# --------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = data.get("message", "")

    if not isinstance(message, str):
        return jsonify({
            "reply": "Please enter a valid text request."
        }), 400

    message = message.strip()

    if not message:
        return jsonify({
            "reply": "Please tell me which PDF you need."
        }), 400

    if len(message) > 500:
        return jsonify({
            "reply": "Please keep your request under 500 characters."
        }), 400

    files = get_pdf_files()

    if not files:
        return jsonify({
            "reply": (
                "No PDFs are available yet. "
                "Please add PDF files to the pdfs folder."
            )
        })

    try:
        filename = match_pdf(message)

        if filename:
            logging.info("Matched PDF: %s", filename)

            return jsonify({
                "reply": f"I found a matching PDF: {filename}",
                "pdf": {
                    "name": filename,
                    "url": "/download/" + filename,
                },
            })

        logging.info(
            "No matching PDF found for request: %s",
            message
        )

        return jsonify({
            "reply": (
                "I couldn't find a matching PDF. "
                "Try the subject name or part of the filename."
            )
        })

    except Exception:
        app.logger.exception("PDF search failed")

        return jsonify({
            "reply": (
                "Sorry, an error occurred while searching "
                "for your PDF. Please try again."
            )
        }), 500


# --------------------------------------------------
# Download a PDF
# --------------------------------------------------

@app.route("/download/<path:filename>", methods=["GET"])
def download_pdf(filename):
    # Only allow filenames returned by our PDF inventory.
    if filename not in get_pdf_files():
        abort(404, description="PDF not found.")

    return send_from_directory(
        str(PDF_FOLDER),
        filename,
        as_attachment=True,
    )


# --------------------------------------------------
# Error handlers
# --------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/download/"):
        return "PDF not found.", 404

    return "Page not found.", 404


@app.errorhandler(413)
def request_too_large(error):
    return jsonify({
        "reply": "Your request is too large."
    }), 413


# --------------------------------------------------
# Run the application
# --------------------------------------------------

app.run(
    host="0.0.0.0",
    port=5000,
    debug=False,
)