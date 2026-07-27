import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import cv2
from flask import Flask, render_template, request, send_file

app = Flask(__name__)
app.secret_key = "demo-upload-db"

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "uploads.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_VIDEO_SIZE_BYTES = 60 * 1024 * 1024


def get_upload_size(uploaded_file) -> int:
    size = uploaded_file.content_length
    if size is None:
        uploaded_file.stream.seek(0, os.SEEK_END)
        size = uploaded_file.stream.tell()
        uploaded_file.stream.seek(0)
    return size or 0


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
        if "media" not in request.files or request.files["media"].filename == "":
            return "No file selected", 400

        uploaded_file = request.files["media"]
        filename = uploaded_file.filename
        mime_type = uploaded_file.mimetype or ""
        file_size = get_upload_size(uploaded_file)
        if mime_type.startswith("video/") and file_size > MAX_VIDEO_SIZE_BYTES:
            return (
                "Video file exceeds 60 MB. For premium subscriptions, unlimited uploads and file size are available for Rs 60 for 1 month.",
                400,
            )
        file_ext = Path(filename).suffix.lower() or ".jpg"
        saved_name = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}{file_ext}"
        save_path = UPLOAD_DIR / saved_name
        uploaded_file.save(save_path)

        output_name = f"{Path(saved_name).stem}_gray{file_ext}"
        output_path = UPLOAD_DIR / output_name

        if mime_type.startswith("video/"):
            cap = cv2.VideoCapture(str(save_path))
            if not cap.isOpened():
                return "Could not open the uploaded video.", 400
            fps = cap.get(cv2.CAP_PROP_FPS) or 24
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))
            if not out.isOpened():
                return "Could not create grayscale video output.", 400
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                out.write(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
            cap.release()
            out.release()
        else:
            image = cv2.imread(str(save_path), cv2.IMREAD_COLOR)
            if image is None:
                return "Could not open the uploaded image.", 400
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            success, encoded = cv2.imencode(".jpg", gray)
            if not success:
                return "Could not create grayscale image output.", 400
            output_path.write_bytes(encoded.tobytes())

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO uploads (filename, mime_type, uploaded_at, file_path) VALUES (?, ?, ?, ?)",
                (filename, mime_type or "application/octet-stream", datetime.now(timezone.utc).isoformat(), str(output_path)),
            )
            conn.commit()

        return send_file(output_path, as_attachment=True, download_name=output_name)

    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
