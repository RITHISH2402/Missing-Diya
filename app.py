
import os
import secrets
import time
from threading import Lock
from urllib.parse import urlparse

from flask import Flask, render_template, request, jsonify

from bot import visit_as_archivist

app = Flask(__name__)

APP_PORT = int(os.environ.get("PORT", "5000"))

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "local-development-only-change-before-deployment",
)

FLAG = os.environ.get(
    "CTF_FLAG",
    "UNI6CTF{when_ayodhya_lost_its_light_rama_returned}",
)

VISIT_TOKEN_TTL = 120
completion_lock = Lock()
pending_visits = {}


def is_allowed_search_url(url):
    """Accept only local search URLs on this service's assigned port."""
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "http"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == APP_PORT
            and parsed.username is None
            and parsed.password is None
            and parsed.path == "/search"
            and not parsed.fragment
        )
    except (ValueError, TypeError):
        return False


def cleanup_expired_visits():
    """Remove expired archivist visits."""
    now = time.time()

    expired = [
        token
        for token, visit in pending_visits.items()
        if now - visit["created_at"] > VISIT_TOKEN_TTL
    ]

    for token in expired:
        pending_visits.pop(token, None)


@app.get("/")
def index():
    return render_template("index.html", app_port=APP_PORT)


@app.get("/search")
def search():
    query = request.args.get("q", "")[:200]

    return render_template(
        "search.html",
        query=query,
        app_port=APP_PORT,
    )


@app.post("/report")
def report():
    submitted_url = request.form.get("url", "").strip()

    if not is_allowed_search_url(submitted_url):
        return jsonify({
            "ok": False,
            "message": "Submit a valid local archive search URL.",
        }), 400

    token = secrets.token_urlsafe(32)

    with completion_lock:
        cleanup_expired_visits()
        pending_visits[token] = {
            "created_at": time.time(),
            "completed": False,
        }

    result = visit_as_archivist(submitted_url, token=token)

    with completion_lock:
        cleanup_expired_visits()
        visit = pending_visits.pop(token, None)
        completed = bool(visit and visit["completed"])

    if not result.get("ok"):
        return jsonify({
            "ok": False,
            "message": result.get(
                "message",
                "The archivist could not inspect that record.",
            ),
        }), 502

    return jsonify({
        "ok": True,
        "message": (
            "The missing diya has been found!"
            if completed
            else "The archivist inspected the record, but found no proof."
        ),
        "completed": completed,
        "flag": FLAG if completed else None,
    })


@app.post("/challenge/callback")
def challenge_callback():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")

    if not isinstance(token, str) or not token:
        return jsonify({"ok": False}), 400

    with completion_lock:
        cleanup_expired_visits()
        visit = pending_visits.get(token)

        if visit is None:
            return jsonify({
                "ok": False,
                "message": "Invalid or expired visit.",
            }), 403

        visit["completed"] = True

    return jsonify({"ok": True})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
