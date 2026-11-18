#!/bin/bash
# macOS / Linux: bấm đúp (hoặc chạy ./run_app.command) để mở giao diện.
# Lần đầu cần: chmod +x run_app.command
cd "$(dirname "$0")" || exit 1

command -v python3 >/dev/null || { echo "Chưa cài Python 3."; exit 1; }
command -v ffmpeg >/dev/null || { echo "Chưa cài ffmpeg (macOS: brew install ffmpeg)."; exit 1; }

if [ ! -d .venv ]; then
  echo "Lần đầu chạy: đang tạo môi trường và cài thư viện..."
  python3 -m venv .venv
  source .venv/bin/activate
  python -m pip install -r requirements.txt
else
  source .venv/bin/activate
fi

python app.py
