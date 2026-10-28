# ============================================================================== 
# vplay_toggle.py - Video Play Toggle
# ============================================================================== 
# Globally turn /vplay on or off without restarting the bot.
# ============================================================================== 

from pyrogram import filters, types

from HasiiMusic import app, db, lang


@app.on_message(filters.command(["enable", "disable"]) & app.sudo_filter)
@lang.language()
async def _toggle_vplay(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass

    if len(m.command) < 2:
        return await m.reply_text(
            "<blockquote><b>Usage:</b>\n"
            "<code>/enable vplay</code>\n"
            "<code>/disable vplay</code></blockquote>"
        )

    feature = m.command[1].strip().lower().lstrip("/")
    if feature != "vplay":
        return

    enable = m.command[0].lower() == "enable"
    current = await db.get_vplay_enabled()

    if current == enable:
        state = "enabled" if enable else "disabled"
        return await m.reply_text(
            f"<blockquote><b>/vplay is already {state}.</b></blockquote>"
        )

    await db.set_vplay_enabled(enable)

    if enable:
        await m.reply_text(
            "<blockquote><b>/vplay has been enabled globally.</b></blockquote>"
        )
    else:
        await m.reply_text(
            "<blockquote><b>/vplay has been disabled globally.</b></blockquote>"
        )
