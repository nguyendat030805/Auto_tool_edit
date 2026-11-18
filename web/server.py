#!/usr/bin/env python3
"""Local HTTP server for the browser-based video and post-template tools."""
from __future__ import annotations

import argparse
import io
import json
import re
import secrets
import shutil
import sys
import mimetypes
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from services.post import MAX_COMMENTS, normalize_template, render_post, validate_image
from services.update import check_for_update
from services.video.web_job import run_job

HERE = Path(__file__).resolve().parents[1]
UI_DIR = HERE / "web" / "ui"
JOBS_DIR = HERE / "jobs"
JOBS: dict[str, dict] = {}
JOBS_LOCK = threading.Lock()
POST_TEMPLATES: dict[str, Path] = {}
POST_CONTENT_IMAGES: dict[str, Path] = {}

# ----------------------------------------------------------------------------
# Job state
# ----------------------------------------------------------------------------


def safe_ext(name: str, default: str) -> str:
    """Return a safe file extension or the supplied fallback."""
    ext = Path(name).suffix.lower()
    return ext if re.fullmatch(r"\.[a-z0-9]{1,5}", ext) else default


def new_job() -> str:
    """Create and register a fresh temporary video job."""
    job_id = secrets.token_hex(8)
    d = JOBS_DIR / job_id
    d.mkdir(parents=True, exist_ok=True)
    with JOBS_LOCK:
        JOBS[job_id] = {"dir": d, "state": "idle", "log": []}
    return job_id


def get_job(job_id: str | None):
    """Look up a job only when its identifier has the expected format."""
    if not job_id or not re.fullmatch(r"[0-9a-f]{16}", job_id):
        return None
    with JOBS_LOCK:
        return JOBS.get(job_id)


# ----------------------------------------------------------------------------
# HTTP server
# ----------------------------------------------------------------------------


class Handler(BaseHTTPRequestHandler):
    """Serve the browser UI and its local upload/render API."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # tắt log mỗi request
        """Keep routine local HTTP requests out of the terminal output."""
        pass

    def _json(self, obj, code: int = 200) -> None:
        """Send a JSON response with the requested HTTP status."""
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _query(self) -> dict:
        """Parse query parameters into a single-value mapping."""
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def do_GET(self) -> None:  # noqa: N802
        """Serve the UI, static assets, job status, or a finished video."""
        path = urlparse(self.path).path
        try:
            if path == "/":
                body = (UI_DIR / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path.startswith("/static/"):
                static_root = (UI_DIR / "static").resolve()
                asset = (static_root / path[len("/static/"):]).resolve()
                try:
                    asset.relative_to(static_root)
                except ValueError:
                    return self._json({"error": "not found"}, 404)
                if not asset.is_file():
                    return self._json({"error": "not found"}, 404)
                body = asset.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(asset.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/update":
                self._json(check_for_update())
            elif path == "/api/status":
                job = get_job(self._query().get("job"))
                if not job:
                    return self._json({"error": "job không tồn tại"}, 404)
                self._json({"state": job["state"], "log": job["log"][-200:]})
            elif path.startswith("/result/"):
                job = get_job(path.rsplit("/", 1)[-1])
                f = job["dir"] / "output.mp4" if job else None
                if not f or not f.exists():
                    return self._json({"error": "chưa có video"}, 404)
                self._send_file(f, "video/mp4")
            else:
                self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _send_file(self, f: Path, ctype: str) -> None:
        """Stream a file and honor byte ranges for browser video playback."""
        size = f.stat().st_size
        start, end, code = 0, size - 1, 200
        rng = self.headers.get("Range", "")
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng)
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                if m.group(2):
                    end = min(int(m.group(2)), size - 1)
            else:
                start = max(size - int(m.group(2)), 0)
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(f, "rb") as fh:
            fh.seek(start)
            left = length
            while left > 0:
                chunk = fh.read(min(1 << 20, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_POST(self) -> None:  # noqa: N802
        """Handle local upload, post-image, and video-job API requests."""
        path = urlparse(self.path).path
        q = self._query()
        try:
            if path == "/api/new":
                self._json({"job": new_job()})
            elif path == "/api/post-template":
                left = int(self.headers.get("Content-Length", "0"))
                if left <= 0 or left > 20 * 1024 * 1024:
                    return self._json({"error": "Template không hợp lệ hoặc vượt quá 20 MB."}, 400)
                template_id = secrets.token_hex(8)
                dest = JOBS_DIR / f"_template_{template_id}.png"
                with open(dest, "wb") as fh:
                    while left > 0:
                        chunk = self.rfile.read(min(1 << 20, left))
                        if not chunk:
                            break
                        fh.write(chunk)
                        left -= len(chunk)
                try:
                    normalize_template(dest)
                except Exception as e:
                    return self._json({"error": f"Không đọc được ảnh template: {e}"}, 400)
                POST_TEMPLATES[template_id] = dest
                self._json({"id": template_id})
            elif path == "/api/post-content-image":
                left = int(self.headers.get("Content-Length", "0"))
                if left <= 0 or left > 20 * 1024 * 1024:
                    return self._json({"error": "Ảnh không hợp lệ hoặc vượt quá 20 MB."}, 400)
                image_id = secrets.token_hex(8)
                dest = JOBS_DIR / f"_post_image_{image_id}.png"
                with open(dest, "wb") as fh:
                    while left > 0:
                        chunk = self.rfile.read(min(1 << 20, left))
                        if not chunk:
                            break
                        fh.write(chunk)
                        left -= len(chunk)
                try:
                    validate_image(dest)
                except Exception as e:
                    return self._json({"error": f"Không đọc được ảnh: {e}"}, 400)
                POST_CONTENT_IMAGES[image_id] = dest
                self._json({"id": image_id})
            elif path == "/api/post-image":
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                data = json.loads(raw.decode("utf-8") or "{}")
                try:
                    raw_c = data.get("comments", [])
                    comments = [str(c) for c in (raw_c if isinstance(raw_c, list) else [])][:MAX_COMMENTS]
                    template_id = data.get("template")
                    template_path = POST_TEMPLATES.get(template_id) if isinstance(template_id, str) else None
                    main_image_id = data.get("main_image")
                    main_image_path = POST_CONTENT_IMAGES.get(main_image_id) if isinstance(main_image_id, str) else None
                    raw_ci = data.get("comment_images", [])
                    comment_image_ids = [str(v) if v else "" for v in (raw_ci if isinstance(raw_ci, list) else [])]
                    comment_image_paths = [POST_CONTENT_IMAGES.get(v) for v in comment_image_ids]
                    img = render_post(str(data.get("main", "")), comments,
                                      "left" if data.get("align") == "left" else "center",
                                      template_path, main_image_path, comment_image_paths)
                except (ValueError, FileNotFoundError, RuntimeError, ImportError) as e:
                    return self._json({"error": str(e)}, 400)
                buf = io.BytesIO()
                img.save(buf, "PNG")
                body = buf.getvalue()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/upload":
                job = get_job(q.get("job"))
                kind, name = q.get("kind"), q.get("name", "")
                if not job or kind not in ("bg", "img", "audio", "sfx", "post", "postaudio", "bgm") or not re.fullmatch(r"\d{1,2}", q.get("idx", "")):
                    return self._json({"error": "yêu cầu không hợp lệ"}, 400)
                idx = int(q["idx"])
                if kind == "bg":
                    dest = job["dir"] / f"bg{safe_ext(name, '.mp4')}"
                elif kind == "sfx":
                    dest = job["dir"] / f"sfx_0{safe_ext(name, '.mp3')}"
                elif kind == "bgm":
                    dest = job["dir"] / f"bgm_0{safe_ext(name, '.mp3')}"
                elif kind == "post":
                    dest = job["dir"] / f"post_0{safe_ext(name, '.png')}"
                elif kind == "postaudio":
                    dest = job["dir"] / f"postaudio_0{safe_ext(name, '.mp3')}"
                elif kind == "img":
                    dest = job["dir"] / f"img_{idx}{safe_ext(name, '.png')}"
                else:
                    dest = job["dir"] / f"audio_{idx}{safe_ext(name, '.mp3')}"
                for old in job["dir"].glob(dest.stem + ".*"):
                    old.unlink(missing_ok=True)
                left = int(self.headers.get("Content-Length", "0"))
                with open(dest, "wb") as fh:
                    while left > 0:
                        chunk = self.rfile.read(min(1 << 20, left))
                        if not chunk:
                            break
                        fh.write(chunk)
                        left -= len(chunk)
                self._json({"ok": True})
            elif path == "/api/run":
                job = get_job(q.get("job"))
                if not job:
                    return self._json({"error": "job không tồn tại"}, 404)
                if job["state"] == "running":
                    return self._json({"error": "đang chạy"}, 409)
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                opts = json.loads(raw.decode("utf-8") or "{}")
                job["state"] = "running"
                job["log"].clear()
                threading.Thread(target=run_job, args=(job, opts), daemon=True).start()
                self._json({"ok": True})
            else:
                self._json({"error": "not found"}, 404)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            try:
                self._json({"error": str(e)}, 500)
            except Exception:  # noqa: BLE001
                pass


def main() -> None:
    """Start the local HTTP server and optionally open the browser."""
    ap = argparse.ArgumentParser(description="Giao diện kéo thả cho tool tạo video đọc comment.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true", help="Không tự mở trình duyệt.")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    if not (HERE / "make_video.py").is_file():
        sys.exit("[LỖI] Không thấy make_video.py. Hãy để app.py cùng thư mục với make_video.py.")

    shutil.rmtree(JOBS_DIR, ignore_errors=True)  # dọn dữ liệu tạm của lần chạy trước
    JOBS_DIR.mkdir(exist_ok=True)

    server = None
    for port in range(args.port, args.port + 20):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        sys.exit("[LỖI] Không mở được cổng nào để chạy giao diện.")

    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Giao diện đang chạy tại: {url}")
    print("Giữ cửa sổ này mở khi dùng tool. Nhấn Ctrl+C để tắt.")
    if not args.no_browser:
        threading.Timer(0.8, webbrowser.open, [url]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã tắt.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()