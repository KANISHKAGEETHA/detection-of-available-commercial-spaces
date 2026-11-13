from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import cv2
import pytesseract
from flask import Flask, flash, redirect, render_template_string, request, url_for
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "spaces.db"
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-development-only")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Commercial Space Finder</title><style>
body{font:16px system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 18px;color:#17212b;background:#f6f8fa}h1{margin-bottom:4px}.muted{color:#52616b}.card{background:white;padding:20px;border-radius:12px;margin:18px 0;box-shadow:0 2px 12px #14212b12}label{display:block;font-weight:600;margin-top:12px}input{padding:9px;width:min(100%,440px);box-sizing:border-box}button{margin-top:16px;padding:10px 18px;background:#145da0;color:white;border:0;border-radius:6px;cursor:pointer}.row{border-top:1px solid #ddd;padding:14px 0}.text{white-space:pre-wrap}.tag{color:#176b42}</style></head><body>
<h1>Commercial Space Finder</h1><div class="muted">Video OCR prototype · review extracted leads before contacting anyone</div>
{% with messages=get_flashed_messages() %}{% for m in messages %}<div class="card">{{m}}</div>{% endfor %}{% endwith %}
<section class="card"><h2>Analyze a video</h2><form method="post" action="{{url_for('analyze')}}" enctype="multipart/form-data"><label>Video file (MP4, AVI, MOV)<input required type="file" name="video" accept="video/mp4,video/avi,video/quicktime"></label><label>Area / location label<input name="location" placeholder="e.g. Erode, Tamil Nadu"></label><label>Latitude (optional)<input name="latitude" type="number" step="any"></label><label>Longitude (optional)<input name="longitude" type="number" step="any"></label><label>Sample interval in seconds<input name="interval" type="number" min="1" max="60" value="3"></label><button>Extract text and save lead</button></form></section>
<section class="card"><h2>Saved leads</h2>{% if spaces %}{% for s in spaces %}<div class="row"><strong>{{s['location'] or 'Unspecified location'}}</strong> <span class="tag">{{s['created_at']}}</span><div class="muted">{% if s['latitude'] is not none and s['longitude'] is not none %}GPS: {{s['latitude']}}, {{s['longitude']}}{% else %}No coordinates supplied{% endif %} · {{s['source']}}</div><p class="text">{{s['ocr_text'] or 'No text detected'}}</p></div>{% endfor %}{% else %}<p class="muted">No leads yet.</p>{% endif %}</section></body></html>"""


def connect() -> sqlite3.Connection:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("""CREATE TABLE IF NOT EXISTS spaces (
        id INTEGER PRIMARY KEY, location TEXT, latitude REAL, longitude REAL,
        source TEXT NOT NULL, ocr_text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    return db


def extract_text(video_path: str, interval: int) -> str:
    capture = cv2.VideoCapture(video_path)
    if not capture.isOpened():
        raise ValueError("The uploaded file could not be opened as a video.")
    fps = capture.get(cv2.CAP_PROP_FPS) or 1
    stride = max(1, int(fps * interval))
    frame_number = 0
    snippets: list[str] = []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_number % stride == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=1.5, fy=1.5)
            text = pytesseract.image_to_string(gray).strip()
            if text and text not in snippets:
                snippets.append(text)
        frame_number += 1
    capture.release()
    return "\n\n--- sampled frame ---\n\n".join(snippets)


@app.get("/")
def index():
    with connect() as db:
        spaces = db.execute("SELECT * FROM spaces ORDER BY id DESC").fetchall()
    return render_template_string(PAGE, spaces=spaces)


@app.post("/analyze")
def analyze():
    uploaded = request.files.get("video")
    if not uploaded or not uploaded.filename:
        flash("Choose a video file first.")
        return redirect(url_for("index"))
    ext = Path(secure_filename(uploaded.filename)).suffix.lower()
    if ext not in {".mp4", ".avi", ".mov", ".mkv"}:
        flash("Supported formats: MP4, AVI, MOV, and MKV.")
        return redirect(url_for("index"))
    interval = min(60, max(1, request.form.get("interval", default=3, type=int)))
    location = request.form.get("location", "").strip()[:200]
    lat = request.form.get("latitude", type=float)
    lon = request.form.get("longitude", type=float)
    if (lat is None) != (lon is None) or (lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180)):
        flash("Enter both valid coordinates, or leave both blank.")
        return redirect(url_for("index"))
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=UPLOAD_DIR, suffix=ext, delete=False) as temp:
            temp_path = temp.name
            uploaded.save(temp)
        text = extract_text(temp_path, interval)
        with connect() as db:
            db.execute("INSERT INTO spaces(location,latitude,longitude,source,ocr_text) VALUES(?,?,?,?,?)",
                       (location, lat, lon, secure_filename(uploaded.filename), text))
        flash("Video analyzed. Review the extracted text for accuracy.")
    except pytesseract.TesseractNotFoundError:
        flash("Tesseract OCR is not installed or not on PATH. Install it and retry.")
    except Exception as exc:
        flash(f"Could not analyze video: {exc}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=False)
