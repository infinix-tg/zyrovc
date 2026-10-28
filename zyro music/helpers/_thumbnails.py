# ==============================================================================
# _thumbnails.py - Thumbnails
# ==============================================================================
# Generates the frosted glass "Now Playing" thumbnails using PIL.
# Runs in a separate thread so it doesn't block the main asyncio loop.
# ==============================================================================

import os
import re
import asyncio
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from HasiiMusic import config
from HasiiMusic.helpers import Track

# Now Playing card: blurred artwork backdrop, square cover on the left,
# title and details on the right. Symbols only, no emoji.
CARD_W, CARD_H = 1280, 720
COVER = 420
COVER_X, COVER_Y = 110, 150
TEXT_X = 600
MAX_TITLE_WIDTH = 600


def trim_to_width(text: str, font: ImageFont.FreeTypeFont, max_w: int) -> str:
    ellipsis = "…"
    if font.getlength(text) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        if font.getlength(text[:i] + ellipsis) <= max_w:
            return text[:i] + ellipsis
    return ellipsis


class Thumbnail:
    def __init__(self):
        try:
            self.title_font = ImageFont.truetype(
                "HasiiMusic/helpers/Raleway-Bold.ttf", 54)
            self.tag_font = ImageFont.truetype(
                "HasiiMusic/helpers/Raleway-Bold.ttf", 24)
            self.regular_font = ImageFont.truetype(
                "HasiiMusic/helpers/Inter-Light.ttf", 28)
        except OSError:
            self.title_font = self.tag_font = self.regular_font = ImageFont.load_default()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
            async with session.get(url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())
            return output_path

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            thumb_url = getattr(song, "thumbnail", "")
            if not thumb_url:
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", song.id):
                    thumb_url = f"https://i.ytimg.com/vi/{song.id}/hqdefault.jpg"
                else:
                    return config.DEFAULT_THUMB

            safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', song.id)[:40]
            temp = f"cache/temp_{safe_id}.jpg"
            output = f"cache/{safe_id}_card.jpg"
            if os.path.exists(output):
                return output

            # Download thumbnail (async operation)
            await self.save_thumb(temp, thumb_url)
            
            # **PERFORMANCE FIX**: Run PIL operations in thread executor to avoid blocking event loop
            # This prevents lag when generating thumbnails for multiple groups simultaneously
            return await asyncio.get_event_loop().run_in_executor(
                None, self._generate_sync, temp, output, song, size
            )
        except Exception:
            return config.DEFAULT_THUMB

    def _wrap(self, text: str, font, max_w: int, lines: int = 2) -> list[str]:
        words, out, cur = text.split(), [], ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if font.getlength(trial) <= max_w:
                cur = trial
            else:
                if cur:
                    out.append(cur)
                cur = w
            if len(out) == lines:
                break
        if cur and len(out) < lines:
            out.append(cur)
        if len(out) == lines and " ".join(out) != text:
            out[-1] = trim_to_width(out[-1] + "…", font, max_w)
        return out or [""]

    def _generate_sync(self, temp: str, output: str, song: Track, size=(1280, 720)) -> str:
        try:
            from HasiiMusic import settings

            with Image.open(temp) as src:
                art = src.convert("RGB")

            # backdrop: the artwork, blurred, darkened, with a soft vignette
            bg = art.resize((CARD_W, CARD_H)).filter(ImageFilter.GaussianBlur(38))
            bg = ImageEnhance.Brightness(bg).enhance(0.45).convert("RGBA")
            shade = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(shade)
            for x in range(CARD_W):
                sd.line([(x, 0), (x, CARD_H)], fill=(0, 0, 0, int(110 * (x / CARD_W))))
            bg = Image.alpha_composite(bg, shade)

            # square cover with a soft shadow
            w, h = art.size
            side = min(w, h)
            cover = art.crop(((w - side) // 2, (h - side) // 2, (w + side) // 2, (h + side) // 2))
            cover = cover.resize((COVER, COVER)).convert("RGBA")
            glow = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
            ImageDraw.Draw(glow).rounded_rectangle(
                (COVER_X, COVER_Y + 16, COVER_X + COVER, COVER_Y + COVER + 16), 36, fill=(0, 0, 0, 170))
            bg = Image.alpha_composite(bg, glow.filter(ImageFilter.GaussianBlur(28)))
            cmask = Image.new("L", (COVER, COVER), 0)
            ImageDraw.Draw(cmask).rounded_rectangle((0, 0, COVER, COVER), 36, fill=255)
            bg.paste(cover, (COVER_X, COVER_Y), cmask)

            d = ImageDraw.Draw(bg)
            white, soft = (255, 255, 255), (214, 214, 224)

            # tag line
            brand = (settings.get("brand_name") or "").upper()
            d.text((TEXT_X, 150), "NOW PLAYING", fill=soft, font=self.tag_font)

            # title (up to two lines)
            clean = re.sub(r"[^\w\s\-&'.,()]+", " ", song.title or "").strip()
            clean = re.sub(r"\s+", " ", clean) or (song.title or "")
            y = 205
            for ln in self._wrap(clean, self.title_font, MAX_TITLE_WIDTH):
                d.text((TEXT_X, y), ln, fill=white, font=self.title_font)
                y += 68

            # details
            meta = []
            if getattr(song, "channel_name", ""):
                meta.append(trim_to_width(song.channel_name, self.regular_font, 420))
            if getattr(song, "view_count", "") and str(song.view_count).isdigit():
                meta.append(f"{int(song.view_count):,} views")
            if meta:
                d.text((TEXT_X, y + 6), "   ·   ".join(meta), fill=soft, font=self.regular_font)

            # equalizer bars (decorative, pure shapes)
            base_y, bx = 470, TEXT_X
            for i, hgt in enumerate([26, 52, 38, 70, 46, 82, 34, 60, 44, 72, 30, 56, 40, 66, 28]):
                d.rounded_rectangle((bx, base_y - hgt, bx + 12, base_y), 5, fill=(255, 255, 255, 235))
                bx += 22

            # duration pill
            is_live = getattr(song, "is_live", False)
            label = "LIVE" if is_live else (song.duration or "")
            pill_w = int(self.regular_font.getlength(label)) + 56
            d.rounded_rectangle((TEXT_X, 510, TEXT_X + pill_w, 566), 28,
                                fill=(255, 64, 64) if is_live else (255, 255, 255))
            d.text((TEXT_X + 28, 523), label, fill=white if is_live else (20, 20, 28), font=self.regular_font)

            # brand mark
            if brand:
                d.text((TEXT_X + pill_w + 28, 525), brand, fill=soft, font=self.tag_font)

            bg.convert("RGB").save(output, "JPEG", quality=90)
            try:
                os.remove(temp)
            except OSError:
                pass
            return output
        except Exception:
            return config.DEFAULT_THUMB
