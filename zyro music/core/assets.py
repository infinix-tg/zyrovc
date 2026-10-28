# ==============================================================================
# assets.py - Generated Placeholder Artwork
# ==============================================================================
# Draws the built in default thumbnail (a dark gradient with a music note) so
# the bot never depends on an outside image host. The owner can replace it
# from the panel at any time.
# ==============================================================================

from PIL import Image, ImageDraw, ImageFilter


def make_default_thumb(path: str, size=(1280, 720)) -> str:
    w, h = size
    img = Image.new("RGB", size)
    px = img.load()
    top, bottom = (46, 20, 92), (8, 8, 20)
    for y in range(h):
        t = y / (h - 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        for x in range(w):
            px[x, y] = row

    # soft glow behind the note
    glow = Image.new("RGB", size, (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    cx, cy = w // 2, h // 2
    gd.ellipse((cx - 260, cy - 260, cx + 260, cy + 260), fill=(110, 60, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    img = Image.blend(img, Image.composite(glow, img, glow.convert("L")), 0.55)

    d = ImageDraw.Draw(img)
    white = (244, 240, 255)
    # beamed pair of eighth notes
    lx, rx = cx - 110, cx + 110
    head_y = cy + 120
    stem_top = cy - 170
    for x in (lx, rx):
        d.ellipse((x - 62, head_y - 44, x + 62, head_y + 44), fill=white)
        d.rectangle((x + 40, stem_top, x + 62, head_y), fill=white)
    d.polygon(
        [(lx + 40, stem_top), (rx + 62, stem_top - 36), (rx + 62, stem_top + 36), (lx + 40, stem_top + 76)],
        fill=white,
    )
    img.save(path, "JPEG", quality=90)
    return path
