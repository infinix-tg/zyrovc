# ==============================================================================
# settings.py - Live Settings Store
# ==============================================================================
# Everything the owner can edit from the panel (/panel) lives here.
#
# - Values are saved in MongoDB, so they survive restarts and redeploys.
# - On boot the saved values are applied on top of config.py / .env defaults.
# - Uploaded pictures are stored in MongoDB too and written back to the local
#   "assets" folder on boot, so hosts with a temporary disk keep them.
# - Edits take effect instantly. No restart is needed.
# ==============================================================================

import asyncio
import io
import os
from dataclasses import dataclass, field
from html import escape
from typing import Any, Optional

from HasiiMusic import app, config, db, logger

ASSET_DIR = "assets"

# ------------------------------------------------------------------------------
# Field registry. The panel is generated from this table, so adding a new
# editable option only takes one new Field(...) line.
# ------------------------------------------------------------------------------


@dataclass
class Field:
    key: str
    label: str
    kind: str                      # text | html | url | int | bool | photo | buttons
    section: str                   # branding | welcome | media | links | limits | features
    default: Any = ""
    attr: Optional[str] = None     # config attribute that mirrors this value
    hint: str = ""
    min: int = 0
    max: int = 10 ** 9
    scale: int = 1                 # config value = stored value * scale


DEFAULT_WELCOME_PM = (
    "<blockquote><b>♪  {brand}</b></blockquote>\n"
    "Hey {user}, ready to play something?\n\n"
    "<blockquote>"
    "◈ <b>Instant playback</b>  songs start in seconds\n"
    "◈ <b>Autoplay</b>  the music never stops\n"
    "◈ <b>YouTube and Spotify</b>  songs, albums, playlists\n"
    "◈ <b>Full control</b>  queue, loop, seek, skip"
    "</blockquote>\n"
    "▸ Add me to a group, start a voice chat and send <code>/play song name</code>\n\n"
    "Crafted by <a href=\"{owner_link}\">{owner}</a>"
)

DEFAULT_WELCOME_GP = (
    "<blockquote><b>♪  {brand}</b></blockquote>\n"
    "Start a voice chat and send <code>/play song name</code>.\n"
    "Autoplay keeps the music going when your queue ends.\n\n"
    "Crafted by <a href=\"{owner_link}\">{owner}</a>"
)

FIELDS: list[Field] = [
    # ---- branding ----
    Field("brand_name", "Bot name", "text", "branding", config.BRAND_NAME, hint="Shown in the welcome message, logs and stats."),
    Field("owner_name", "Owner name", "text", "branding", config.OWNER_NAME, hint="Your name. Shown on the welcome message and the Owner button."),
    Field("owner_link", "Owner link", "url", "branding", config.OWNER_LINK, hint="Link for your name, e.g. https://t.me/yourusername. Leave empty to link your Telegram profile."),
    # ---- welcome ----
    Field("welcome_pm", "Private welcome", "html", "welcome", DEFAULT_WELCOME_PM, hint="Sent when someone opens the bot in private."),
    Field("welcome_gp", "Group welcome", "html", "welcome", DEFAULT_WELCOME_GP, hint="Sent when /start is used in a group."),
    Field("help_text", "Help header", "html", "welcome", "", hint="Optional text above the help buttons. Empty keeps the built in text."),
    # ---- media ----
    Field("start_img", "Welcome picture", "photo", "media", config.START_IMG, "START_IMG"),
    Field("help_img", "Help picture", "photo", "media", "", hint="Empty reuses the welcome picture."),
    Field("ping_img", "Ping and stats picture", "photo", "media", config.PING_IMG, "PING_IMG"),
    Field("thumb_img", "Default thumbnail", "photo", "media", config.DEFAULT_THUMB, "DEFAULT_THUMB", hint="Used for now playing when no artwork exists."),
    Field("radio_img", "Radio picture", "photo", "media", config.RADIO_IMG, "RADIO_IMG"),
    # ---- links ----
    Field("support_chat", "Support chat", "url", "links", config.SUPPORT_CHAT, "SUPPORT_CHAT"),
    Field("support_channel", "Updates channel", "url", "links", config.SUPPORT_CHANNEL, "SUPPORT_CHANNEL"),
    Field("source_url", "Source button", "url", "links", "", hint="Empty hides the Source button."),
    Field("extra_buttons", "Extra buttons", "buttons", "links", [], hint="One per line: Label | https://link"),
    # ---- limits ----
    Field("duration_limit", "Max duration (minutes)", "int", "limits", config.DURATION_LIMIT // 60, "DURATION_LIMIT", min=1, max=100000, scale=60),
    Field("queue_limit", "Queue limit", "int", "limits", config.QUEUE_LIMIT, "QUEUE_LIMIT", min=1, max=500),
    Field("playlist_limit", "Playlist batch size", "int", "limits", config.PLAYLIST_LIMIT, "PLAYLIST_LIMIT", min=1, max=200),
    Field("playlist_max", "Playlist max songs", "int", "limits", config.PLAYLIST_MAX, "PLAYLIST_MAX", min=1, max=1000),
    Field("video_max_height", "Video height", "int", "limits", config.VIDEO_MAX_HEIGHT, "VIDEO_MAX_HEIGHT", min=0, max=1080, hint="0 means unlimited, otherwise 360 to 1080."),
    # ---- animation ----
    Field("anim_style", "Loading animation", "choice", "animation", config.ANIMATION_STYLE, hint="Shown while a song is searched, downloaded and started."),
    # ---- features ----
    Field("autoplay", "Autoplay (default)", "bool", "features", config.AUTOPLAY, "AUTOPLAY", hint="Default for every chat. Admins can switch it per chat with /autoplay."),
    Field("auto_leave", "Auto leave", "bool", "features", config.AUTO_LEAVE, "AUTO_LEAVE"),
    Field("queue_end_message", "Queue end message", "bool", "features", config.QUEUE_END_MESSAGE, "QUEUE_END_MESSAGE"),
    Field("thumb_gen", "Thumbnail generator", "bool", "features", config.THUMB_GEN, "THUMB_GEN"),
]
BY_KEY = {f.key: f for f in FIELDS}


def parse_buttons(raw: str) -> list[list[str]]:
    """Turn 'Label | url' lines into [[label, url], ...]. Raises ValueError."""
    rows = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            raise ValueError(f"Missing '|' in: {line}")
        label, url = (p.strip() for p in line.split("|", 1))
        if not label or not _valid_url(url):
            raise ValueError(f"Bad label or link in: {line}")
        rows.append([label[:32], url])
    if len(rows) > 6:
        raise ValueError("Maximum 6 extra buttons.")
    return rows


def _valid_url(url: str) -> bool:
    return url.startswith(("https://", "http://", "tg://"))


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("@"):
        raw = f"https://t.me/{raw[1:]}"
    elif raw.startswith(("t.me/", "telegram.me/")):
        raw = "https://" + raw
    return raw


class Settings:
    def __init__(self):
        self.values: dict[str, Any] = {}
        self.assets = db.db.assets

    # -------------------------------------------------------------- reading
    def get(self, key: str) -> Any:
        if key in self.values:
            return self.values[key]
        return BY_KEY[key].default

    def is_custom(self, key: str) -> bool:
        return key in self.values

    @property
    def owner_link(self) -> str:
        return self.get("owner_link") or f"tg://user?id={config.OWNER_ID}"

    def photo(self, key: str) -> str:
        """Path or URL ready to hand to Telegram, or an empty string."""
        val = self.get(key)
        if isinstance(val, str) and val.startswith("asset:"):
            path = self._path(val[6:])
            return path if os.path.exists(path) else ""
        return val or ""

    def start_photo(self) -> str:
        return self.photo("start_img")

    def help_photo(self) -> str:
        return self.photo("help_img") or self.photo("start_img")

    def render(self, template: str, user=None) -> str:
        """Fill {placeholders}. Plain replace so HTML braces never break."""
        first = escape(getattr(user, "first_name", "") or "there")
        mention = getattr(user, "mention", None) or first
        ctx = {
            "{user}": first,
            "{mention}": mention,
            "{bot}": escape(app.name or self.get("brand_name")),
            "{brand}": escape(self.get("brand_name")),
            "{owner}": escape(self.get("owner_name")),
            "{owner_link}": self.owner_link,
            "{username}": f"@{app.username}" if app.username else "",
        }
        for k, v in ctx.items():
            template = template.replace(k, v)
        return template

    def welcome(self, private: bool, user=None) -> str:
        return self.render(self.get("welcome_pm" if private else "welcome_gp"), user)

    # -------------------------------------------------------------- writing
    async def load(self) -> None:
        doc = await db.cache.find_one({"_id": "panel_settings"})
        self.values = {k: v for k, v in (doc or {}).get("values", {}).items() if k in BY_KEY}

        os.makedirs(ASSET_DIR, exist_ok=True)
        async for a in self.assets.find():
            try:
                with open(self._path(a["_id"]), "wb") as fh:
                    fh.write(a["data"])
            except Exception as e:
                logger.warning(f"Could not restore asset {a.get('_id')}: {e}")
        self._ensure_default_thumb()
        self.apply()
        logger.info(f"Panel settings loaded ({len(self.values)} custom values).")

    async def _save(self) -> None:
        await db.cache.update_one(
            {"_id": "panel_settings"}, {"$set": {"values": self.values}}, upsert=True
        )

    async def set(self, key: str, value: Any) -> None:
        self.values[key] = value
        await self._save()
        self.apply()

    async def reset(self, key: str) -> None:
        self.values.pop(key, None)
        if BY_KEY[key].kind == "photo":
            await self._drop_asset(key)
        await self._save()
        self.apply()

    async def reset_all(self) -> None:
        for key in list(self.values):
            if BY_KEY[key].kind == "photo":
                await self._drop_asset(key)
        self.values.clear()
        await self._save()
        self.apply()

    # -------------------------------------------------------------- pictures
    def _path(self, key: str) -> str:
        return os.path.join(ASSET_DIR, f"{key}.jpg")

    async def set_photo_bytes(self, key: str, raw: bytes) -> None:
        data = await asyncio.get_running_loop().run_in_executor(None, _to_jpeg, raw)
        os.makedirs(ASSET_DIR, exist_ok=True)
        with open(self._path(key), "wb") as fh:
            fh.write(data)
        await self.assets.update_one({"_id": key}, {"$set": {"data": data}}, upsert=True)
        await self.set(key, f"asset:{key}")

    async def set_photo_url(self, key: str, url: str) -> None:
        await self._drop_asset(key)
        await self.set(key, url)

    async def _drop_asset(self, key: str) -> None:
        await self.assets.delete_one({"_id": key})
        try:
            os.remove(self._path(key))
        except OSError:
            pass

    def _ensure_default_thumb(self) -> None:
        from HasiiMusic.core.assets import make_default_thumb

        path = os.path.join(ASSET_DIR, "default_thumb.jpg")
        if not os.path.exists(path):
            try:
                make_default_thumb(path)
            except Exception as e:
                logger.warning(f"Could not create default thumbnail: {e}")

    # -------------------------------------------------------------- applying
    def apply(self) -> None:
        """Mirror every value onto config so the rest of the bot just works."""
        for f in FIELDS:
            if not f.attr:
                continue
            val = self.photo(f.key) if f.kind == "photo" else self.get(f.key)
            if f.kind == "int":
                val = int(val) * f.scale
            setattr(config, f.attr, val)

        # the generated placeholder keeps now playing working with no upload
        fallback = os.path.join(ASSET_DIR, "default_thumb.jpg")
        if not config.DEFAULT_THUMB and os.path.exists(fallback):
            config.DEFAULT_THUMB = fallback

        # limits are clamped the same way config.py does
        h = config.VIDEO_MAX_HEIGHT
        config.VIDEO_MAX_HEIGHT = 0 if h <= 0 else max(360, min(h, 1080))

        # support links fall back to the owner so buttons and texts never break
        if not config.SUPPORT_CHAT:
            config.SUPPORT_CHAT = self.owner_link
        app.name = self.get("brand_name")


def _to_jpeg(raw: bytes) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        im.thumbnail((2560, 2560))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=92)
        return out.getvalue()
