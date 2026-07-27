import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, render_template, request

app = Flask(__name__)
app.secret_key = "demo-upload-db"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "uploads.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                file_path TEXT NOT NULL
            )
            """
        )
        conn.commit()


init_db()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if "photo" not in request.files or request.files["photo"].filename == "":
            return "No file selected", 400

        uploaded_file = request.files["photo"]
        filename = uploaded_file.filename
        file_ext = Path(filename).suffix or ".jpg"
        saved_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}{file_ext}"
        save_path = UPLOAD_DIR / saved_name
        uploaded_file.save(save_path)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO uploads (filename, mime_type, uploaded_at, file_path) VALUES (?, ?, ?, ?)",
                (filename, uploaded_file.mimetype or "application/octet-stream", datetime.now(timezone.utc).isoformat(), str(save_path)),
            )
            conn.commit()

        return f"Uploaded successfully. File saved as {saved_name}", 200

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
