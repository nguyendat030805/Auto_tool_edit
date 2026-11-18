#!/usr/bin/env python3
"""
post_template.py - Tạo ảnh "bài viết" từ template có sẵn.

Template mặc định (templates/post_template.jpg) có 1 ô lớn + các ô comment. Module này cho phép
dùng 0, 1, 2 hoặc 3 comment (tối đa MAX_COMMENTS): các khung tự co giãn theo nội dung,
ô comment tự cao lên theo độ dài chữ, chữ tự xuống dòng và tự chỉnh cỡ cho vừa ô.

Dùng thử nhanh:
    python post_template.py --main "Nội dung bài viết" --comment "Comment 1" --comment "Comment 2" --out bai_viet.png

Dùng trong code:
    from post_template import render_post
    img = render_post("Nội dung bài viết", ["Comment 1", "Comment 2"])
    img.save("bai_viet.png")

Font: ưu tiên fonts/regular.ttf và fonts/bold.ttf (nếu bạn tự bỏ vào), nếu không có thì dùng font hệ thống
hỗ trợ tiếng Việt (Segoe UI/Arial/Tahoma trên Windows, Arial trên macOS, DejaVu/Liberation trên Linux).

Lưu ý: toạ độ bên dưới đã đo cho đúng template đi kèm. Nếu đổi sang template khác (khác bố cục)
thì phải đo lại các hằng số trong phần HÌNH HỌC.
"""
from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

HERE = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = HERE / "templates" / "post_template.jpg"
FONTS_DIR = HERE / "fonts"

MAX_COMMENTS = 3
MAX_MAIN_CHARS = 1500
MAX_COMMENT_CHARS = 500

# ----------------------------------------------------------------------------
# HÌNH HỌC (toạ độ trên template gốc 1122 x 1402)
# ----------------------------------------------------------------------------
TPL_W, TPL_H = 1122, 1402

# Dải ruột ô lớn chỉ có nền trơn hai bên -> co giãn dọc được mà không làm méo icon
STRETCH_A, STRETCH_B = 310, 590
# Khối cố định: từ STRETCH_B tới FIXED_END (có icon giỏ hàng, biểu đồ, túi, đồng xu)
FIXED_END = 905
# Từ TAIL_START trở xuống là phần trang trí (điện thoại, cột biểu đồ) giữ nguyên
TAIL_START = 1115
# Hàng bắt đầu khu vực ô comment trên template
SLOT_TOP = 800

# Khung chữ của ô lớn (trên template gốc, đối xứng quanh tâm ô x=566)
MAIN_RECT_X0, MAIN_RECT_X1 = 150, 982
MAIN_RECT_TOP, MAIN_RECT_BOTTOM = 268, 712

# Ô comment: vùng cắt gốc (gồm cả quầng sáng neon), cắt 9-slice theo chiều dọc
PANEL_X0, PANEL_X1 = 125, 1000
PANEL_Y0, PANEL_Y1 = 796, 953          # cao 157
PANEL_CAP_TOP, PANEL_CAP_BOTTOM = 60, 60
PANEL_NATIVE_INTERIOR = 123            # chiều cao ruột sáng của ô comment gốc
PANEL_GAP = 9                          # khoảng cách giữa 2 vùng cắt liền kề
PANEL_INTERIOR_X0, PANEL_INTERIOR_X1 = 138, 983
TAIL_OVERLAP = 4

# Màu chữ
MAIN_COLOR = (28, 22, 84)
COMMENT_COLOR = (36, 30, 92)

# ----------------------------------------------------------------------------
# Font
# ----------------------------------------------------------------------------


def _font_candidates(bold: bool) -> list[Path]:
    """List local custom and platform fonts in preferred fallback order."""
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    names_win = ["segoeuib.ttf", "arialbd.ttf", "tahomabd.ttf"] if bold else ["segoeui.ttf", "arial.ttf", "tahoma.ttf"]
    mac = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"] if bold else \
          ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf"]
    lin = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
           "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"] if bold else \
          ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
           "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
           "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"]
    custom = [FONTS_DIR / ("bold.ttf" if bold else "regular.ttf"),
              FONTS_DIR / ("bold.otf" if bold else "regular.otf")]
    return custom + [win / n for n in names_win] + [Path(p) for p in mac + lin]


@lru_cache(maxsize=None)
def _font_path(bold: bool) -> str:
    """Find a usable font path, falling back from bold to regular."""
    for p in _font_candidates(bold):
        if p.is_file():
            return str(p)
    if bold:  # không có bản đậm thì dùng bản thường
        return _font_path(False)
    raise RuntimeError(
        "Không tìm thấy font hỗ trợ tiếng Việt. Hãy bỏ file font vào thư mục 'fonts' "
        "với tên regular.ttf (và bold.ttf nếu muốn chữ đậm).")


@lru_cache(maxsize=None)
def get_font(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    """Load and cache the requested font face and size."""
    return ImageFont.truetype(_font_path(bold), size)


# ----------------------------------------------------------------------------
# Xử lý chữ
# ----------------------------------------------------------------------------
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\u2300-\u23FF\uFE00-\uFE0F\u200D\u20E3\U000E0020-\U000E007F]")


def clean_text(text: str) -> str:
    """Bỏ emoji (font thường không vẽ được), gọn khoảng trắng nhưng giữ xuống dòng."""
    text = _EMOJI_RE.sub("", str(text or "")).replace("\r\n", "\n").replace("\r", "\n").replace("\t", " ")
    lines = [" ".join(line.split()) for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_w: float) -> list[str]:
    """Wrap text to a maximum width, splitting words that are too long."""
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            lines.append("")
            continue
        cur = ""
        for w in words:
            while font.getlength(w) > max_w:       # từ quá dài -> cắt theo ký tự
                k = len(w)
                while k > 1 and font.getlength(w[:k]) > max_w:
                    k -= 1
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(w[:k])
                w = w[k:]
            test = f"{cur} {w}".strip()
            if cur and font.getlength(test) > max_w:
                lines.append(cur)
                cur = w
            else:
                cur = test
        lines.append(cur)
    return lines


def line_height(size: int) -> int:
    """Calculate the vertical spacing for a font size."""
    return int(size * 1.28)


def draw_block(draw: ImageDraw.ImageDraw, lines: list[str], font, size: int, color,
               rect: tuple[int, int, int, int], align: str) -> None:
    """Vẽ khối chữ canh giữa theo chiều dọc trong rect (x0, y0, x1, y1)."""
    x0, y0, x1, y1 = rect
    lh = line_height(size)
    block_h = len(lines) * lh
    y = y0 + (y1 - y0 - block_h) / 2
    for line in lines:
        if line:
            if align == "left":
                draw.text((x0, y), line, font=font, fill=color, anchor="la")
            else:
                draw.text(((x0 + x1) / 2, y), line, font=font, fill=color, anchor="ma")
        y += lh


# ----------------------------------------------------------------------------
# Nền sạch (xoá 2 ô comment khỏi template)
# ----------------------------------------------------------------------------


def _row_strip(img: Image.Image, x0: int, x1: int, ya: int, yb: int, blur: int = 8) -> Image.Image:
    """Trung bình các hàng ya..yb thành 1 hàng màu (x1-x0 điểm), làm mượt theo chiều ngang."""
    w = x1 - x0
    s = img.crop((x0, ya, x1, yb)).resize((w, 1), Image.BOX).resize((w, 9), Image.NEAREST)
    return s.filter(ImageFilter.GaussianBlur(blur)).crop((0, 4, w, 5))


def _decay_mask(w: int, h: int, length: float, from_left: bool) -> Image.Image:
    """Mặt nạ đậm ở mép và nhạt dần vào giữa (dùng để hoà màu mép vào phần nền điền)."""
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for x in range(w):
        dist = x if from_left else (w - 1 - x)
        v = int(255 * math.exp(-dist / length))
        if v:
            d.line([(x, 0), (x, h)], fill=v)
    return m


def make_clean_plate(tpl: Image.Image) -> Image.Image:
    """Điền lại nền thay cho 2 ô comment.

    Màu ở giữa nội suy dọc từ nền ngay trên ô comment 1 xuống nền ngay dưới ô comment 2;
    sát hai mép trái/phải thì lấy đúng màu nền bên cạnh rồi mờ dần vào giữa, nên không lộ mép chữ nhật.
    """
    plate = tpl.copy()
    x0, x1, y0, y1 = 116, 1008, 794, 1120
    w, h = x1 - x0, y1 - y0
    top = _row_strip(tpl, x0, x1, 787, 795)       # nền ngay phía trên ô comment 1
    bot = _row_strip(tpl, x0, x1, 1121, 1125)     # nền ngay phía dưới ô comment 2
    two = Image.new("RGB", (w, 2))
    two.paste(top, (0, 0))
    two.paste(bot, (0, 1))
    center = two.resize((w, h), Image.BILINEAR)

    def side(xa: int, xb: int) -> Image.Image:
        """Create a blurred vertical color strip sampled from one side."""
        col = tpl.crop((xa, y0, xb, y1)).resize((1, h), Image.BOX)
        col = col.resize((9, h), Image.NEAREST).filter(ImageFilter.GaussianBlur(7)).crop((4, 0, 5, h))
        return col.resize((w, h), Image.NEAREST)

    fill = Image.composite(side(x0 - 14, x0 - 2), center, _decay_mask(w, h, 70, True))
    fill = Image.composite(side(x1 + 2, x1 + 14), fill, _decay_mask(w, h, 45, False))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle([4, 3, w - 5, h - 4], fill=255)
    plate.paste(fill, (x0, y0), mask.filter(ImageFilter.GaussianBlur(2)))
    return plate


@lru_cache(maxsize=2)
def _load_template(path: str, mtime: float) -> tuple[Image.Image, Image.Image]:
    """Load a template, normalize its dimensions, and build its clean plate."""
    with Image.open(path) as source:
        source.load()
        original = source.convert("RGB")
    if original.size != (TPL_W, TPL_H):
        fitted = ImageOps.contain(original, (TPL_W, TPL_H), method=Image.Resampling.LANCZOS)
        corner = original.getpixel((0, 0))
        tpl = Image.new("RGB", (TPL_W, TPL_H), corner)
        tpl.paste(fitted, ((TPL_W - fitted.width) // 2, (TPL_H - fitted.height) // 2))
        original.close()
    else:
        tpl = original
    return tpl, make_clean_plate(tpl)


# ----------------------------------------------------------------------------
# Dựng ảnh
# ----------------------------------------------------------------------------


def _tail_slice(plate: Image.Image, n: int) -> Image.Image:
    """Dải nền giữa khối cố định và phần trang trí dưới cùng, co/cắt cho đúng n hàng."""
    native = TAIL_START - FIXED_END
    src = plate.crop((0, FIXED_END, TPL_W, TAIL_START))
    if n == native:
        return src
    if n > native:
        return src.resize((TPL_W, n), Image.BICUBIC)
    top = plate.crop((0, FIXED_END, TPL_W, FIXED_END + n))
    bot = plate.crop((0, TAIL_START - n, TPL_W, TAIL_START))
    f = min(n, 60)
    ramp = Image.linear_gradient("L").resize((TPL_W, f), Image.BILINEAR)   # đen -> trắng theo chiều dọc
    mask = Image.new("L", (TPL_W, n), 0)
    mask.paste(ramp, (0, n - f))
    return Image.composite(bot, top, mask)


def _make_panel(tpl: Image.Image, interior: int) -> Image.Image:
    """Ô comment cao theo nội dung: co cả hai đầu và đoạn giữa theo tỷ lệ 9-slice."""
    box = tpl.crop((PANEL_X0, PANEL_Y0, PANEL_X1, PANEL_Y1))
    w, h = box.size
    target_h = max(72, interior + (PANEL_Y1 - PANEL_Y0) - PANEL_NATIVE_INTERIOR)
    top_h = max(1, round(PANEL_CAP_TOP * target_h / h))
    bot_h = max(1, round(PANEL_CAP_BOTTOM * target_h / h))
    mid_h = max(1, target_h - top_h - bot_h)
    top = box.crop((0, 0, w, PANEL_CAP_TOP))
    mid = box.crop((0, PANEL_CAP_TOP, w, h - PANEL_CAP_BOTTOM))
    bot = box.crop((0, h - PANEL_CAP_BOTTOM, w, h))
    top = top.resize((w, top_h), Image.BICUBIC)
    mid = mid.resize((w, mid_h), Image.BICUBIC)
    bot = bot.resize((w, bot_h), Image.BICUBIC)
    out = Image.new("RGB", (w, target_h))
    out.paste(top, (0, 0))
    out.paste(mid, (0, top.height))
    out.paste(bot, (0, top.height + mid.height))
    return out


def render_post(main_text: str, comments: list[str] | None = None, align: str = "center",
                template: Path | str | None = None, main_image: Path | str | None = None,
                comment_images: list[Path | str] | None = None) -> Image.Image:
    """Trả về ảnh PIL (RGB). Canvas giữ 1122x1402 nếu đủ chỗ, tự cao thêm khi chữ quá dài."""
    path = Path(template) if template else TEMPLATE_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Không thấy template: {path}")
    tpl, plate = _load_template(str(path), path.stat().st_mtime)

    main = clean_text(main_text)[:MAX_MAIN_CHARS]
    main_img = Path(main_image) if main_image else None
    if main_img and not main_img.is_file():
        raise FileNotFoundError(f"Không thấy ảnh bài viết chính: {main_img}")
    if not main and not main_img:
        raise ValueError("Chưa có nội dung bài viết chính.")

    cms = [clean_text(c)[:MAX_COMMENT_CHARS] for c in (comments or [])]
    supplied_images = [Path(p) if p else None for p in (comment_images or [])]
    entries: list[tuple[str, Path | None]] = []
    for i, text in enumerate(cms[:MAX_COMMENTS]):
        image = supplied_images[i] if i < len(supplied_images) else None
        if image and not image.is_file():
            raise FileNotFoundError(f"Không thấy ảnh comment: {image}")
        if text or image:
            entries.append((text, image))
    k = len(entries)
    align = "left" if align == "left" else "center"

    # --- bố cục từng ô comment
    text_w = PANEL_INTERIOR_X1 - PANEL_INTERIOR_X0 - 2 * 46
    cinfo = []
    for c, image in entries:
        if image:
            with Image.open(image).convert("RGBA") as source:
                w, h = source.size
                max_w = text_w + 92
                scaled_h = max(48, min(420, round(h * max_w / w)))
            size = 36
            lines = []
            interior = scaled_h
        else:
            size = 36
            lines = wrap_text(c, get_font(size, False), text_w)
            while len(lines) > 4 and size > 26:
                size -= 2
                lines = wrap_text(c, get_font(size, False), text_w)
            interior = max(48, len(lines) * line_height(size) + 24)
        cinfo.append(dict(lines=lines, size=size, interior=interior, image=image))

    panel_h = [max(72, ci["interior"] + (PANEL_Y1 - PANEL_Y0) - PANEL_NATIVE_INTERIOR) for ci in cinfo]
    rel_end = (-(SLOT_TOP - PANEL_Y0) + sum(panel_h) + PANEL_GAP * (k - 1)) if k else 0
    fixed_rows = FIXED_END - SLOT_TOP
    tail_native = TAIL_START - FIXED_END
    s4 = max(0, rel_end - TAIL_OVERLAP - fixed_rows) if k else 0

    # --- bố cục chữ ô lớn
    native_band = STRETCH_B - STRETCH_A
    total_flex = native_band + tail_native              # a_new + s4 = 490 khi giữ canvas 1402
    rect_native_h = MAIN_RECT_BOTTOM - MAIN_RECT_TOP
    avail_rect_h = rect_native_h + (total_flex - native_band)
    rect_w = MAIN_RECT_X1 - MAIN_RECT_X0

    chosen = None
    if not main_img:
        for size in range(68, 33, -2):
            lines = wrap_text(main, get_font(size, True), rect_w)
            if len(lines) * line_height(size) + 24 <= avail_rect_h:
                chosen = (size, lines)
                break
        if chosen is None:
            size = 34
            chosen = (size, wrap_text(main, get_font(size, True), rect_w))
    msize = chosen[0] if chosen else 34
    mlines = chosen[1] if chosen else []
    need_rect_h = len(mlines) * line_height(msize) + 24 if mlines else 24
    if main_img:
        with Image.open(main_img).convert("RGBA") as source:
            iw, ih = source.size
        need_rect_h = max(48, round(rect_w * ih / iw))
    need_rect_h = max(48, need_rect_h)
    a_new = max(40, native_band + (need_rect_h - rect_native_h))

    # --- ghép các dải của template
    fixed_top = STRETCH_A + 0
    tail_h = TPL_H - TAIL_START
    out_h = fixed_top + a_new + (FIXED_END - STRETCH_B) + s4 + tail_h
    out = Image.new("RGB", (TPL_W, out_h))
    out.paste(plate.crop((0, 0, TPL_W, STRETCH_A)), (0, 0))
    out.paste(plate.crop((0, STRETCH_A, TPL_W, STRETCH_B)).resize((TPL_W, a_new), Image.BICUBIC), (0, STRETCH_A))
    y = STRETCH_A + a_new
    out.paste(plate.crop((0, STRETCH_B, TPL_W, FIXED_END)), (0, y))
    slot_y = y + (SLOT_TOP - STRETCH_B)                  # hàng của SLOT_TOP trên ảnh mới
    y += FIXED_END - STRETCH_B
    if s4:
        out.paste(_tail_slice(plate, s4), (0, y))
        y += s4
    out.paste(plate.crop((0, TAIL_START, TPL_W, TPL_H)), (0, y))

    # --- chữ ô lớn
    draw = ImageDraw.Draw(out)
    rect = (MAIN_RECT_X0, MAIN_RECT_TOP, MAIN_RECT_X1,
            MAIN_RECT_BOTTOM + (a_new - native_band))
    if mlines:
        draw_block(draw, mlines, get_font(msize, True), msize, MAIN_COLOR, rect, align)
    elif main_img:
        with Image.open(main_img).convert("RGBA") as source:
            iw, ih = source.size
            scale = min((MAIN_RECT_X1 - MAIN_RECT_X0) / iw, (rect[3] - rect[1]) / ih)
            tw, th = max(1, round(iw * scale)), max(1, round(ih * scale))
            fitted = source.resize((tw, th), Image.LANCZOS)
            tx = rect[0] + ((rect[2] - rect[0]) - tw) // 2
            ty = rect[1] + ((rect[3] - rect[1]) - th) // 2
            out.paste(fitted, (tx, ty), fitted)

    # --- ô comment
    top = slot_y - (SLOT_TOP - PANEL_Y0)
    for ci, ph in zip(cinfo, panel_h):
        panel = _make_panel(tpl, ci["interior"])
        region = out.crop((PANEL_X0, top, PANEL_X1, top + ph))
        out.paste(ImageChops.lighter(region, panel), (PANEL_X0, top))
        interior_top = top + max(8, round(15 * ph / (PANEL_Y1 - PANEL_Y0)))
        trect = (PANEL_INTERIOR_X0 + 46, interior_top, PANEL_INTERIOR_X1 - 46, interior_top + ci["interior"])
        if ci["image"]:
            with Image.open(ci["image"]).convert("RGBA") as source:
                iw, ih = source.size
                max_w = trect[2] - trect[0]
                max_h = trect[3] - trect[1]
                scale = min(max_w / iw, max_h / ih)
                tw, th = max(1, round(iw * scale)), max(1, round(ih * scale))
                fitted = source.resize((tw, th), Image.LANCZOS)
                tx = trect[0] + (max_w - tw) // 2
                ty = trect[1] + (max_h - th) // 2
                out.paste(fitted, (tx, ty), fitted)
        else:
            draw_block(draw, ci["lines"], get_font(ci["size"], False), ci["size"], COMMENT_COLOR, trect, align)
        top += ph + PANEL_GAP
    return out


