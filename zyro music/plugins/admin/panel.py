# ==============================================================================
# panel.py - Owner Panel
# ==============================================================================
# /panel opens a control center for the bot owner, entirely inside Telegram.
#
#   Branding   bot name, owner name, owner link
#   Welcome    private / group welcome text (full Telegram formatting), help text
#   Media      welcome, help, ping, thumbnail and radio pictures (upload or link)
#   Animation  loading animation shown before a song starts (pick + live preview)
#   Links      support chat, channel, source button, extra custom buttons
#   Limits     duration, queue, playlist and video limits
#   Features   auto leave, queue end message, thumbnails, /vplay, logger
#   Access     sudo users, blocked users, blacklisted chats
#   System     stats, logs, restart, reset
#
# Everything is saved to MongoDB and applied instantly (see core/settings.py).
# Only OWNER_ID can open it.
# ==============================================================================

import asyncio
import os
import re
import shutil
import sys
import time
from html import escape

import psutil
from pyrogram import filters, types
from pyrogram.errors import MessageNotModified, QueryIdInvalid

from HasiiMusic import app, boot, config, db, lang, logger, settings, stop, userbot
from HasiiMusic.core import animations
from HasiiMusic.core.settings import BY_KEY, FIELDS, normalize_url, parse_buttons
from HasiiMusic.helpers import buttons as ui

# ------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------

OWNER = filters.create(
    lambda _, __, u: bool(getattr(u, "from_user", None)) and u.from_user.id == app.owner
)

# user_id -> {"action": str, "key": str | None, "panel": message_id}
pending: dict[int, dict] = {}

DIVIDER = "─" * 18
SECTIONS = {
    "branding": "Branding",
    "welcome": "Welcome",
    "media": "Media",
    "animation": "Animation",
    "links": "Links",
    "limits": "Limits",
    "features": "Features",
    "access": "Access",
    "system": "System",
}
PLACEHOLDERS = "{user} {mention} {brand} {owner} {owner_link} {username}"


def b(text: str, data: str) -> types.InlineKeyboardButton:
    return types.InlineKeyboardButton(text, callback_data=data)


def kb(rows) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(rows)


def back(section: str | None = None):
    return [b("« Back", f"op:sec:{section}" if section else "op:home")]


def plain(html: str, limit: int = 60) -> str:
    text = re.sub(r"<[^>]+>", "", html or "").replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return escape(text[:limit] + ("..." if len(text) > limit else ""))


def show(key: str) -> str:
    f, val = BY_KEY[key], settings.get(key)
    tail = "" if settings.is_custom(key) else " <i>(default)</i>"
    if f.kind == "bool":
        return "ON" if val else "OFF"
    if f.kind == "photo":
        if isinstance(val, str) and val.startswith("asset:"):
            return "uploaded"
        return "link" if val else "not set"
    if f.kind == "buttons":
        return f"{len(val)} button(s)" if val else "none"
    if f.kind == "html":
        return (plain(val) or "empty") + tail
    if f.kind == "int":
        return f"<code>{val}</code>{tail}"
    if f.kind == "choice":
        return f"<code>{animations.STYLES[animations.style_key(val)][0]}</code>{tail}"
    return (f"<code>{escape(str(val))}</code>" if val else "not set") + tail


def line(key: str) -> str:
    return f"♫ <b>{BY_KEY[key].label}</b>\n    {show(key)}"


def head(title: str) -> str:
    return f"<b>♪ {title.upper()} ♪</b>\n{DIVIDER}\n"


async def edit(chat_id: int, msg_id: int, text: str, markup=None) -> None:
    try:
        await app.edit_message_text(chat_id, msg_id, text, reply_markup=markup)
    except MessageNotModified:
        pass


def fmt_uptime(seconds: int) -> str:
    d, r = divmod(seconds, 86400)
    h, r = divmod(r, 3600)
    m = r // 60
    return (f"{d}d " if d else "") + f"{h}h {m}m"


# ------------------------------------------------------------------------------
# screens
# ------------------------------------------------------------------------------


async def home_view():
    text = (
        f"{head('Owner Panel')}"
        f"<blockquote>"
        f"♫ <b>Bot</b>  {escape(settings.get('brand_name'))}\n"
        f"♫ <b>Owner</b>  {escape(settings.get('owner_name'))}\n"
        f"♫ <b>Uptime</b>  {fmt_uptime(int(time.time() - boot))}\n"
        f"♫ <b>Groups</b>  {len(await db.get_chats())}    <b>Users</b>  {len(await db.get_users())}\n"
        f"♫ <b>Playing now</b>  {len(db.active_calls)}    <b>Assistants</b>  {len(userbot.clients)}"
        f"</blockquote>\n"
        f"Pick a section to edit. Every change is saved and applied instantly."
    )
    names = list(SECTIONS.items())
    rows = []
    for i in range(0, len(names), 2):
        rows.append([b(f"♪ {label}", f"op:sec:{key}") for key, label in names[i:i + 2]])
    rows.append([b("Close panel", "op:close")])
    return text, kb(rows)


def edit_rows(keys: list[str], extra=None):
    rows, row = [], []
    for k in keys:
        row.append(b(BY_KEY[k].label, f"op:edit:{k}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows + (extra or [])


async def section_view(name: str, note: str = ""):
    keys = [f.key for f in FIELDS if f.section == name]
    prefix = f"<i>{note}</i>\n\n" if note else ""

    if name == "branding":
        text = head("Branding") + prefix + "\n".join(line(k) for k in keys)
        return text, kb(edit_rows(keys, [back()]))

    if name == "welcome":
        text = (
            head("Welcome") + prefix + "\n".join(line(k) for k in keys)
            + f"\n\nPlaceholders: <code>{PLACEHOLDERS}</code>"
        )
        rows = edit_rows(keys)
        rows += [
            [b("Preview private", "op:prev:welcome_pm"), b("Preview group", "op:prev:welcome_gp")],
            [b("Reset private", "op:reset:welcome_pm"), b("Reset group", "op:reset:welcome_gp")],
            back(),
        ]
        return text, kb(rows)

    if name == "media":
        text = head("Media") + prefix + "\n".join(line(k) for k in keys)
        rows = [[b(BY_KEY[k].label, f"op:media:{k}")] for k in keys]
        return text, kb(rows + [back()])

    if name == "animation":
        cur = animations.style_key(settings.get("anim_style"))
        text = head("Animation") + prefix + (
            "Shown while a song is searched, downloaded and started.\n"
            "Pick a style. Use <b>Preview</b> to watch it before you decide.\n\n"
            f"<blockquote>♫ <b>Current</b>  {animations.STYLES[cur][0]}\n"
            f"♫ <b>Sample</b>\n{animations.STYLES[cur][1][len(animations.STYLES[cur][1]) // 2]}</blockquote>"
        )
        rows = []
        for key, (label, _frames) in animations.STYLES.items():
            dot = "●" if key == cur else "○"
            rows.append([b(f"{dot} {label}", f"op:anim:{key}"), b("Preview", f"op:aprev:{key}")])
        rows.append([b("Reset to default", "op:reset:anim_style")])
        rows.append(back())
        return text, kb(rows)

    if name == "links":
        text = head("Links") + prefix + "\n".join(line(k) for k in keys)
        btns = settings.get("extra_buttons")
        if btns:
            text += "\n<blockquote>" + "\n".join(f"{escape(l)}  →  {escape(u)}" for l, u in btns) + "</blockquote>"
        rows = edit_rows(keys, [[b("Clear extra buttons", "op:clear:extra_buttons")], back()])
        return text, kb(rows)

    if name == "limits":
        text = head("Limits") + prefix + "\n".join(line(k) for k in keys)
        return text, kb(edit_rows(keys, [back()]))

    if name == "features":
        vplay = await db.get_vplay_enabled()
        logger_on = await db.get_logger()
        text = head("Features") + prefix + (
            "<blockquote>"
            + "\n".join(f"♫ <b>{BY_KEY[k].label}</b>  {show(k)}" for k in keys)
            + f"\n♫ <b>Video play (/vplay)</b>  {'ON' if vplay else 'OFF'}"
            + f"\n♫ <b>Play logger</b>  {'ON' if logger_on else 'OFF'}"
            + "</blockquote>\nTap a feature to switch it."
        )
        dot = lambda on: "●" if on else "○"
        rows = [[b(f"{dot(settings.get(k))} {BY_KEY[k].label}", f"op:tog:{k}")] for k in keys]
        rows.append([b(f"{dot(vplay)} Video play", "op:tog:vplay"), b(f"{dot(logger_on)} Play logger", "op:tog:logger")])
        return text, kb(rows + [back()])

    if name == "access":
        sudoers = [u for u in app.sudoers if u != app.owner]
        lst = "\n".join(f"♫ <code>{u}</code>" for u in sudoers) or "none"
        text = head("Access") + prefix + (
            f"<b>Sudo users</b>\n<blockquote>{lst}</blockquote>\n"
            f"<b>Blocked users</b>  {len(app.bl_users)}\n"
            f"<b>Blacklisted chats</b>  {len(db.blacklisted)}"
        )
        rows = [[b("Add sudo", "op:act:sudo_add")]]
        for u in sudoers[:6]:
            rows.append([b(f"Remove sudo {u}", f"op:sudo_rm:{u}")])
        rows += [
            [b("Block user", "op:act:block"), b("Unblock user", "op:act:unblock")],
            [b("Blacklist chat", "op:act:bl_chat"), b("Whitelist chat", "op:act:wl_chat")],
            back(),
        ]
        return text, kb(rows)

    if name == "system":
        mem = psutil.virtual_memory()
        text = head("System") + prefix + (
            "<blockquote>"
            f"♫ <b>CPU</b>  {psutil.cpu_percent(interval=0.3)}%\n"
            f"♫ <b>RAM</b>  {round(mem.used / 1024 ** 3, 1)} / {round(mem.total / 1024 ** 3, 1)} GB\n"
            f"♫ <b>Uptime</b>  {fmt_uptime(int(time.time() - boot))}\n"
            f"♫ <b>Python</b>  {sys.version.split()[0]}"
            "</blockquote>"
        )
        rows = [
            [b("Send logs", "op:do:logs"), b("Restart bot", "op:ask:restart")],
            [b("Reset every setting", "op:ask:reset_all")],
            back(),
        ]
        return text, kb(rows)

    return await home_view()


def media_view(key: str, note: str = ""):
    f = BY_KEY[key]
    prefix = f"<i>{note}</i>\n\n" if note else ""
    text = head(f.label) + prefix + f"Status  {show(key)}\n" + (f"\n{f.hint}" if f.hint else "")
    rows = [
        [b("Upload picture", f"op:edit:{key}"), b("Preview", f"op:prev:{key}")],
        [b("Remove", f"op:reset:{key}")],
        back("media"),
    ]
    return text, kb(rows)


def prompt_view(key: str):
    f = BY_KEY[key]
    cur = settings.get(key)
    text = head(f"Edit {f.label}")
    if f.hint:
        text += f"{f.hint}\n\n"

    if f.kind == "photo":
        text += "Send a <b>picture</b> (as photo or file) or an <b>image link</b>."
    elif f.kind == "html":
        text += (
            "Send the new text. Use Telegram's own formatting (bold, italic, quote, links).\n"
            f"Placeholders: <code>{PLACEHOLDERS}</code>\n\n<b>Current</b>\n<pre>{escape((cur or '')[:1500])}</pre>"
        )
    elif f.kind == "int":
        text += f"Send a number from {f.min} to {f.max}.\n\n<b>Current</b>  <code>{cur}</code>"
    elif f.kind == "buttons":
        text += "Send one button per line:\n<code>Label | https://link</code>\nSend <code>-</code> to remove all."
    elif f.kind == "url":
        text += f"Send a link or @username. Send <code>-</code> to clear.\n\n<b>Current</b>  <code>{escape(str(cur) or 'not set')}</code>"
    else:
        text += f"Send the new value.\n\n<b>Current</b>  <code>{escape(str(cur))}</code>"
    text += "\n\nSend /cancel to stop."
    back_to = f"op:media:{key}" if f.kind == "photo" else f"op:sec:{f.section}"
    return text, kb([[b("Reset to default", f"op:reset:{key}"), b("Cancel", back_to)]])


ACTION_PROMPTS = {
    "sudo_add": "Send the <b>user ID</b> or @username to make sudo.",
    "block": "Send the <b>user ID</b> or @username to block.",
    "unblock": "Send the <b>user ID</b> or @username to unblock.",
    "bl_chat": "Send the <b>chat ID</b> to blacklist (starts with -100).",
    "wl_chat": "Send the <b>chat ID</b> to whitelist.",
}


# ------------------------------------------------------------------------------
# commands
# ------------------------------------------------------------------------------


@app.on_message(filters.command(["animation", "animations"]) & filters.private & OWNER)
async def open_animation(_, m: types.Message):
    pending.pop(m.from_user.id, None)
    text, markup = await section_view("animation")
    await m.reply_text(text, reply_markup=markup)


@app.on_message(filters.command(["panel", "owner"]) & filters.private & OWNER)
async def open_panel(_, m: types.Message):
    pending.pop(m.from_user.id, None)
    try:
        await m.delete()
    except Exception:
        pass
    text, markup = await home_view()
    await m.reply_text(text, reply_markup=markup)


@app.on_message(filters.command(["panel", "owner"]) & ~OWNER & filters.private)
async def panel_denied(_, m: types.Message):
    await m.reply_text("<blockquote>This panel is only for the bot owner.</blockquote>")


# ------------------------------------------------------------------------------
# button presses
# ------------------------------------------------------------------------------


async def goto_field_screen(q: types.CallbackQuery, key: str, note: str = ""):
    f = BY_KEY[key]
    if f.kind == "photo":
        text, markup = media_view(key, note)
    else:
        text, markup = await section_view(f.section, note)
    await edit(q.message.chat.id, q.message.id, text, markup)


@app.on_callback_query(filters.regex(r"^op:") & OWNER)
async def panel_cb(_, q: types.CallbackQuery):
    parts = q.data.split(":")
    cmd, arg = parts[1], (parts[2] if len(parts) > 2 else "")
    uid, chat_id, msg_id = q.from_user.id, q.message.chat.id, q.message.id

    try:
        if cmd != "edit" and cmd != "act":
            pending.pop(uid, None)

        if cmd == "home":
            text, markup = await home_view()
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "close":
            await q.message.delete()

        elif cmd == "sec":
            text, markup = await section_view(arg)
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "media":
            text, markup = media_view(arg)
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "edit":
            pending[uid] = {"action": "field", "key": arg, "panel": msg_id}
            text, markup = prompt_view(arg)
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "act":
            pending[uid] = {"action": arg, "key": None, "panel": msg_id}
            await edit(chat_id, msg_id, head("Access") + ACTION_PROMPTS[arg] + "\n\nSend /cancel to stop.",
                       kb([back("access")]))

        elif cmd == "tog":
            if arg == "vplay":
                await db.set_vplay_enabled(not await db.get_vplay_enabled())
                text, markup = await section_view("features", "Saved")
            elif arg == "logger":
                await db.set_logger(not await db.get_logger())
                text, markup = await section_view("features", "Saved")
            else:
                await settings.set(arg, not settings.get(arg))
                text, markup = await section_view("features", "Saved")
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "reset":
            await settings.reset(arg)
            await goto_field_screen(q, arg, "Reset to default")

        elif cmd == "clear":
            await settings.set(arg, [])
            await goto_field_screen(q, arg, "Cleared")

        elif cmd == "anim":
            if arg in animations.STYLES:
                await settings.set("anim_style", arg)
            text, markup = await section_view("animation", "Saved")
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "aprev":
            await q.answer()
            await preview_animation(chat_id, msg_id, arg)
            return

        elif cmd == "prev":
            await send_preview(chat_id, arg)

        elif cmd == "sudo_rm":
            uid_rm = int(arg)
            app.sudoers.discard(uid_rm)
            app.sudo_filter.discard(uid_rm)
            await db.del_sudo(uid_rm)
            text, markup = await section_view("access", "Sudo user removed")
            await edit(chat_id, msg_id, text, markup)

        elif cmd == "ask":
            label = "Restart the bot now?" if arg == "restart" else "Reset every panel setting to its default? Uploaded pictures are deleted."
            await edit(chat_id, msg_id, head("Confirm") + label,
                       kb([[b("Yes", f"op:do:{arg}"), b("No", "op:sec:system")]]))

        elif cmd == "do":
            await run_system_action(q, arg)
            return

        await q.answer()
    except QueryIdInvalid:
        pass
    except Exception as e:
        logger.error(f"Panel error ({q.data}): {e}", exc_info=True)
        try:
            await q.answer(f"Error: {str(e)[:150]}", show_alert=True)
        except Exception:
            pass


_previewing: set[int] = set()


async def preview_animation(chat_id: int, msg_id: int, style: str) -> None:
    """Play a style on the panel message for a few seconds, then restore it."""
    if style not in animations.STYLES or msg_id in _previewing:
        return
    _previewing.add(msg_id)
    try:
        stages = ["search"] * 3 + ["download"] * 3 + ["start"] * 3
        for i, stage in enumerate(stages):
            text = head("Preview") + animations.render(i, stage, "Your song name", style)
            await edit(chat_id, msg_id, text, kb([[b("Stop preview", "op:sec:animation")]]))
            await asyncio.sleep(1.2)
    except Exception:
        pass
    finally:
        _previewing.discard(msg_id)
    text, markup = await section_view("animation")
    await edit(chat_id, msg_id, text, markup)


async def send_preview(chat_id: int, key: str):
    if key in ("welcome_pm", "welcome_gp"):
        private = key == "welcome_pm"
        user = await app.get_users(app.owner)
        text = settings.welcome(private, user)
        l = await lang.get_lang(chat_id)
        markup = ui.start_key(l, private)
        photo = settings.start_photo()
        try:
            if photo:
                return await app.send_photo(chat_id, photo, caption=text, reply_markup=markup)
        except Exception:
            pass
        return await app.send_message(chat_id, text, reply_markup=markup)

    photo = settings.photo(key)
    if not photo:
        return await app.send_message(chat_id, "<blockquote>No picture set.</blockquote>")
    try:
        await app.send_photo(chat_id, photo, caption=f"<b>{BY_KEY[key].label}</b>")
    except Exception as e:
        await app.send_message(chat_id, f"<blockquote>Could not send this picture: {escape(str(e)[:200])}</blockquote>")


async def run_system_action(q: types.CallbackQuery, action: str):
    chat_id, msg_id = q.message.chat.id, q.message.id
    if action == "logs":
        await q.answer()
        if os.path.exists("log.txt"):
            await app.send_document(chat_id, "log.txt", caption=f"{escape(settings.get('brand_name'))} logs")
        else:
            await app.send_message(chat_id, "<blockquote>No log file yet.</blockquote>")
    elif action == "reset_all":
        await settings.reset_all()
        await q.answer("Everything reset")
        text, markup = await section_view("system", "All settings reset")
        await edit(chat_id, msg_id, text, markup)
    elif action == "restart":
        await q.answer("Restarting")
        await edit(chat_id, msg_id, head("System") + "Restarting. Back in a few seconds.")
        shutil.rmtree("cache", ignore_errors=True)
        asyncio.create_task(stop())
        await asyncio.sleep(2)
        os.execl(sys.executable, sys.executable, "-m", "HasiiMusic")


# ------------------------------------------------------------------------------
# receiving the owner's next message (value to save)
# ------------------------------------------------------------------------------


def _has_pending(_, __, m: types.Message) -> bool:
    if not m.from_user or m.from_user.id not in pending:
        return False
    text = m.text or ""
    return not text.startswith("/") or text.split()[0].lower().startswith("/cancel")


@app.on_message(filters.private & OWNER & filters.create(_has_pending), group=-10)
async def receive_value(_, m: types.Message):
    m.stop_propagation()
    uid = m.from_user.id
    state = pending[uid]
    chat_id, panel_id = m.chat.id, state["panel"]

    async def done(markup_text: str, markup, drop_state: bool = True):
        if drop_state:
            pending.pop(uid, None)
        try:
            await m.delete()
        except Exception:
            pass
        await edit(chat_id, panel_id, markup_text, markup)

    async def fail(msg: str):
        # keep waiting so the owner can try again
        try:
            await m.delete()
        except Exception:
            pass
        text, markup = (prompt_view(state["key"]) if state["key"] else (None, None))
        if text:
            await edit(chat_id, panel_id, f"<i>{escape(msg)}</i>\n\n{text}", markup)
        else:
            await edit(chat_id, panel_id, f"<i>{escape(msg)}</i>\n\nTry again or send /cancel.", kb([back("access")]))

    if (m.text or "").lower().startswith("/cancel"):
        text, markup = await home_view()
        return await done(text, markup)

    try:
        if state["action"] == "field":
            key = state["key"]
            f = BY_KEY[key]
            note = await save_field(m, f)
            if isinstance(note, tuple):
                return await fail(note[1])
            if f.kind == "photo":
                text, markup = media_view(key, note)
            else:
                text, markup = await section_view(f.section, note)
            return await done(text, markup)

        note = await run_access_action(m, state["action"])
        if isinstance(note, tuple):
            return await fail(note[1])
        text, markup = await section_view("access", note)
        await done(text, markup)
    except Exception as e:
        logger.error(f"Panel input error: {e}", exc_info=True)
        await fail(f"Something went wrong: {e}")


async def save_field(m: types.Message, f):
    """Validate and store one field. Returns a note, or ("err", message)."""
    key = f.key

    if f.kind == "photo":
        media = m.photo or (m.document if m.document and (m.document.mime_type or "").startswith("image/") else None)
        if media:
            if getattr(media, "file_size", 0) and media.file_size > 10 * 1024 * 1024:
                return ("err", "That picture is over 10 MB.")
            buf = await app.download_media(m, in_memory=True)
            await settings.set_photo_bytes(key, buf.getvalue())
            return "Picture saved"
        url = normalize_url(m.text or "")
        if url.startswith(("http://", "https://")):
            await settings.set_photo_url(key, url)
            return "Picture link saved"
        return ("err", "Send a picture or an http(s) link.")

    if not m.text and not m.caption:
        return ("err", "Please send text.")
    raw_plain = (m.text or m.caption or "").strip()

    if f.kind == "html":
        html = (m.text.html if m.text else m.caption.html).strip()
        if f.key != "help_text" and not html:
            return ("err", "The text cannot be empty.")
        if len(html) > 3500:
            return ("err", "Too long. Keep it under 3500 characters.")
        await settings.set(key, html)
        return "Saved"

    if f.kind == "text":
        value = re.sub(r"[<>&]", "", raw_plain)[:48]
        if not value:
            return ("err", "The value cannot be empty.")
        await settings.set(key, value)
        return "Saved"

    if f.kind == "url":
        if raw_plain in ("-", "none"):
            await settings.set(key, "")
            return "Cleared"
        url = normalize_url(raw_plain)
        if not url.startswith(("https://", "http://", "tg://")):
            return ("err", "That is not a valid link. Use https://... or @username.")
        await settings.set(key, url)
        return "Saved"

    if f.kind == "int":
        try:
            n = int(raw_plain)
        except ValueError:
            return ("err", "Send a whole number.")
        if not f.min <= n <= f.max:
            return ("err", f"Use a number from {f.min} to {f.max}.")
        await settings.set(key, n)
        return "Saved"

    if f.kind == "buttons":
        if raw_plain == "-":
            await settings.set(key, [])
            return "Cleared"
        try:
            rows = parse_buttons(raw_plain)
        except ValueError as e:
            return ("err", str(e))
        await settings.set(key, rows)
        return "Saved"

    return ("err", "This field cannot be edited here.")


async def resolve_user(m: types.Message):
    sender = getattr(m, "forward_from", None) or getattr(
        getattr(m, "forward_origin", None), "sender_user", None
    )
    if sender:
        return sender
    raw = (m.text or "").strip()
    ref = int(raw) if re.fullmatch(r"-?\d{5,15}", raw) else raw
    return await app.get_users(ref)


async def run_access_action(m: types.Message, action: str):
    raw = (m.text or "").strip()

    if action in ("bl_chat", "wl_chat"):
        if not re.fullmatch(r"-\d{5,20}", raw):
            return ("err", "Chat IDs look like -1001234567890.")
        chat_id = int(raw)
        if action == "bl_chat":
            if chat_id in db.blacklisted:
                return ("err", "That chat is already blacklisted.")
            await db.add_blacklist(chat_id)
            return "Chat blacklisted"
        if chat_id not in db.blacklisted:
            return ("err", "That chat is not blacklisted.")
        await db.del_blacklist(chat_id)
        return "Chat whitelisted"

    try:
        user = await resolve_user(m)
    except Exception:
        return ("err", "Could not find that user.")

    if action == "sudo_add":
        if user.id in app.sudoers:
            return ("err", "That user is already sudo.")
        app.sudoers.add(user.id)
        app.sudo_filter.update([user.id])
        await db.add_sudo(user.id)
        return f"{plain(user.first_name)} is now sudo"

    if action == "block":
        if user.id in app.sudoers:
            return ("err", "Sudo users cannot be blocked.")
        if user.id in app.bl_users:
            return ("err", "That user is already blocked.")
        app.bl_users.add(user.id)
        await db.add_blacklist(user.id)
        return f"{plain(user.first_name)} blocked"

    if action == "unblock":
        if user.id not in app.bl_users:
            return ("err", "That user is not blocked.")
        app.bl_users.discard(user.id)
        await db.del_blacklist(user.id)
        return f"{plain(user.first_name)} unblocked"

    return ("err", "Unknown action.")
