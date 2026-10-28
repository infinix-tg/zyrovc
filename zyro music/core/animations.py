# ==============================================================================
# animations.py - Loading Animations
# ==============================================================================
# The animated "please wait" message shown while a song is searched, downloaded
# and started. Symbols only, no emojis.
#
# - The owner picks the style live from /panel -> Animation (or /animation).
# - The animation runs in its own task, so it never slows the music down.
# - It stops on its own the moment the real message replaces it, on any
#   Telegram error, or after MAX_SECONDS.
# ==============================================================================

import asyncio
import math
from html import escape
from typing import Optional

from pyrogram import errors

TICK = 1.3          # seconds between edits (stays well inside Telegram limits)
MAX_SECONDS = 60    # hard stop so a stuck download can never edit forever
DEFAULT_STYLE = "equalizer"

_SC = str.maketrans(
    "abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ",
)


def sc(text: str) -> str:
    """Small caps, matching the rest of the bot's look."""
    return text.lower().translate(_SC)


def _equalizer() -> list[str]:
    bars = "▁▂▃▄▅▆▇█"
    frames = []
    for t in range(10):
        frames.append("".join(
            bars[int((math.sin(t * 0.8 + i * 0.9) + 1) / 2 * 7)] for i in range(8)
        ))
    return frames


def _scanner() -> list[str]:
    n = 7
    path = list(range(n)) + list(range(n - 2, 0, -1))
    return ["".join("●" if i == p else "·" for i in range(n)) for p in path]


def _notes() -> list[str]:
    seq = ["♩", "♪", "♫", "♬"]
    return [" ".join(seq[(i + t) % 4] for i in range(3)) for t in range(4)]


def _fill() -> list[str]:
    n = 8
    return ["▰" * k + "▱" * (n - k) for k in range(n + 1)]


# key -> (display name, frames)
STYLES: dict[str, tuple[str, list[str]]] = {
    "equalizer": ("Equalizer", _equalizer()),
    "vinyl": ("Vinyl", ["◐", "◓", "◑", "◒"]),
    "pulse": ("Pulse", ["◌", "○", "◎", "◉", "●", "◉", "◎", "○"]),
    "orbit": ("Orbit", ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]),
    "scanner": ("Scanner", _scanner()),
    "notes": ("Notes", _notes()),
    "fill": ("Fill bar", _fill()),
    "still": ("Still (no animation)", ["♪"]),
}

STAGES = {
    "search": ("searching", 2),
    "download": ("downloading", 4),
    "start": ("starting stream", 6),
    "next": ("loading next track", 4),
    "auto": ("autoplay · finding a similar song", 2),
}


def style_key(key: Optional[str] = None) -> str:
    if key is None:
        from HasiiMusic import settings
        key = settings.get("anim_style")
    return key if key in STYLES else DEFAULT_STYLE


def render(frame: int, stage: str, query: str = "", style: Optional[str] = None) -> str:
    key = style_key(style)
    frames = STYLES[key][1]
    label, filled = STAGES.get(stage, STAGES["search"])
    symbol = frames[frame % len(frames)]
    bar = "▰" * filled + "▱" * (6 - filled)
    text = f"<blockquote><b>{symbol}   {sc(label)}</b>\n{bar}</blockquote>"
    query = (query or "").strip()
    if query:
        text += f"\n<blockquote>♪ {escape(query[:48])}{'...' if len(query) > 48 else ''}</blockquote>"
    return text


# message key -> running animator, so any code can stop the animation of a
# message just before it edits or deletes that message.
_active: dict[tuple[int, int], "Animator"] = {}


def _key(message) -> Optional[tuple[int, int]]:
    try:
        return (message.chat.id, message.id)
    except Exception:
        return None


async def stop_for(message) -> None:
    if not message:
        return
    anim = _active.get(_key(message))
    if anim:
        await anim.stop()


class Animator:
    def __init__(self, query: str = "", style: Optional[str] = None):
        self.query = query
        self.style = style_key(style)
        self.stage = "search"
        self.message = None
        self._task: Optional[asyncio.Task] = None
        self._stopped = False

    def first_text(self, stage: str = "search") -> str:
        self.stage = stage
        return render(0, stage, self.query, self.style)

    def start(self, message, stage: Optional[str] = None) -> None:
        """Begin animating `message`. A single frame style never edits."""
        if not message or len(STYLES[self.style][1]) < 2:
            return
        self.message = message
        if stage:
            self.stage = stage
        k = _key(message)
        if k:
            _active[k] = self
        self._task = asyncio.create_task(self._run())

    def set_stage(self, stage: str) -> None:
        self.stage = stage

    async def stop(self) -> None:
        self._stopped = True
        k = _key(self.message) if self.message else None
        if k and _active.get(k) is self:
            _active.pop(k, None)
        task, self._task = self._task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def _run(self) -> None:
        frames = STYLES[self.style][1]
        i, last, elapsed = 0, "", 0.0
        try:
            while not self._stopped and elapsed < MAX_SECONDS:
                await asyncio.sleep(TICK)
                elapsed += TICK
                i += 1
                text = render(i % len(frames), self.stage, self.query, self.style)
                if text == last or self._stopped:
                    continue
                try:
                    await self.message.edit_text(text)
                    last = text
                except errors.MessageNotModified:
                    pass
                except Exception:
                    # message gone, flood wait, no rights: just stop quietly
                    break
        except asyncio.CancelledError:
            pass
        finally:
            k = _key(self.message) if self.message else None
            if k and _active.get(k) is self:
                _active.pop(k, None)
