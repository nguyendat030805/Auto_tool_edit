Tool tạo video "đọc comment" tự động

Đầu vào: 1 video nền + 3-4 ảnh chụp comment (+ lời đọc của từng comment). Đầu ra: 1 video dọc 1080x1920 — mỗi comment hiện lên (trượt + mờ dần), có giọng đọc TTS, video nền tự lặp/cắt cho vừa độ dài giọng đọc.

Cài đặt
Cài ffmpeg (phải gọi được ffmpeg và ffprobe trong terminal).
Windows: winget install ffmpeg hoặc tải từ ffmpeg.org rồi thêm vào PATH
macOS: brew install ffmpeg
Ubuntu: sudo apt install ffmpeg
Cài thư viện Python:
pip install -r requirements.txt

Cấu trúc code

- `web/server.py`: HTTP server và API cho giao diện.
- `web/ui/`: HTML, CSS và JavaScript của trình duyệt (được tách riêng).
- `services/video/`: xử lý media, giọng đọc, audio, render video và CLI.
- `services/post/`: dựng ảnh bài viết và xử lý template tải lên.
- `app.py`, `make_video.py`, `post_template.py`: entry point tương thích với cách chạy cũ.

Các hàm Python trong service có docstring mô tả nhiệm vụ; JavaScript giao diện có chú thích cho các hàm chính.

Cách dùng 1: giao diện kéo thả (khuyên dùng)
Windows: bấm đúp run_app.bat
macOS/Linux: chạy ./run_app.command (lần đầu cần chmod +x run_app.command)

Lần đầu file sẽ tự tạo môi trường và cài thư viện. Sau đó trình duyệt tự mở trang tool (mặc định http://127.0.0.1:8765). Kéo video nền và ảnh comment vào, gõ lời đọc (hoặc kéo file audio có sẵn), bấm Tạo video, xem và tải video ngay trên trang. Giữ cửa sổ lệnh mở trong lúc dùng; đóng nó là tắt tool.

Tạo bài viết từ template (tab "Tạo bài viết từ template")

Chỉ cần copy/dán hoặc tải nội dung bài viết chính và 0 đến 3 comment, tool tự đặt chữ vào template. Có thể dùng template mặc định `templates/post_template.jpg` hoặc tải một template PNG khác từ máy:

Số ô không cố định: bấm + Thêm comment hoặc Xoá tuỳ ý. Ô lớn tự co giãn theo số comment còn lại, ô comment tự cao lên theo độ dài chữ.
Chữ tự xuống dòng, tự chỉnh cỡ cho vừa ô. Chữ quá dài thì ảnh được kéo cao thêm thay vì bị cắt.
Xem trước tự cập nhật khi gõ. Bấm Tải ảnh về để lưu PNG, hoặc Đưa vào tool làm video để dùng luôn làm bài viết chính.
Emoji bị bỏ qua vì font không vẽ được.
Font: tự dùng Segoe UI / Arial / Tahoma (Windows). Muốn dùng font riêng, bỏ regular.ttf (và bold.ttf) vào thư mục fonts.
Cấu trúc bài viết giờ được tính theo kích thước thực tế của chữ hoặc ảnh: ô bài viết chính và ô comment co giãn sát nội dung, không giữ chiều cao thừa cứng.
Nội dung có thể dán bằng nút "Dán văn bản" hoặc tải file `.txt`, `.md`, `.csv`; mỗi ô comment có nút tải/dán riêng.
Có thể dán/tải ảnh trực tiếp cho bài viết chính hoặc từng comment bằng nút "Dán ảnh"/"Tải ảnh". Hình ảnh được giữ tỷ lệ và đặt vừa khung tương ứng.
Template tải lên có thể là PNG với nhiều kích thước. Ảnh được tự giữ tỷ lệ và điều chỉnh vào khung chuẩn 1122 x 1402; phần dư được lấy màu từ góc ảnh để không làm méo bố cục.

Dùng bằng dòng lệnh: python post_template.py --main "Nội dung" --comment "Comment 1" --comment "Comment 2" --out bai_viet.png

Template mặc định nằm tại `templates/post_template.jpg`. `post_template.py` vẫn được giữ làm lệnh tương thích; phần dựng ảnh nằm trong `services/post/`.

Cách dùng 2: dòng lệnh

Chuẩn bị file texts.txt, mỗi dòng là lời đọc của 1 comment, đúng thứ tự ảnh:

Video này hay quá, cảm ơn bạn đã chia sẻ
Mình đã thử làm theo và thành công luôn
Có ai biết cách nào nhanh hơn không ạ

Chạy:

python make_video.py --bg nen.mp4 --comments c1.png c2.png c3.png --texts texts.txt --out ket_qua.mp4
Tuỳ chọn hay dùng
Tuỳ chọn	Ý nghĩa
--voice vi-VN-NamMinhNeural	Giọng nam (mặc định vi-VN-HoaiMyNeural, giọng nữ)
--rate +10%	Đọc nhanh hơn (-10% để chậm lại)
--dim 0.3	Làm tối video nền để comment dễ đọc (0 = giữ nguyên)
--gap 0.8	Khoảng nghỉ giữa các comment (giây)
--offset-y -200	Đẩy ảnh comment lên cao (âm) hoặc xuống thấp (dương)
--card-width 0.85	Độ rộng ảnh comment so với khung
--size 1920x1080	Đổi sang video ngang
--tts-engine gtts / pyttsx3	TTS dự phòng (pip install gTTS / pyttsx3)
Không muốn gõ texts.txt?

Có thể để tool OCR chữ từ ảnh (bỏ --texts). Cần cài thêm Tesseract và gói tiếng Việt (vie) và pip install pytesseract. Dùng --ocr-only để xem trước chữ OCR, sửa lỗi rồi lưu vào texts.txt, vì OCR hay sai dấu tiếng Việt.

Lưu ý
edge-tts cần internet khi chạy (dùng giọng neural của Microsoft Edge, miễn phí).
Ảnh comment nên là ảnh chụp rõ, nền sáng; tool tự bo góc và đổ bóng.
Muốn thêm: nhạc nền, phụ đề chạy chữ, chạy hàng loạt nhiều video, là các bước mở rộng dễ thêm vào make_video.py.