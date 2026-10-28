# ==============================================================================
# autoplay.py - Autoplay Toggle
# ==============================================================================
# /autoplay [on|off] switches autoplay for this chat. When the queue runs out,
# the bot picks a similar song and keeps the music going.
# ==============================================================================

from pyrogram import filters, types

from HasiiMusic import app, db, lang
from HasiiMusic.helpers import can_manage_vc


@app.on_message(filters.command(["autoplay"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _autoplay(_, m: types.Message):
    try:
        await m.delete()
    except Exception:
        pass

    current = await db.get_autoplay(m.chat.id)
    if len(m.command) > 1:
        arg = m.command[1].lower()
        if arg in ("on", "enable", "1", "yes"):
            new = True
        elif arg in ("off", "disable", "0", "no"):
            new = False
        else:
            return await m.reply_text(m.lang["autoplay_usage"])
    else:
        new = not current

    await db.set_autoplay(m.chat.id, new)
    await m.reply_text(m.lang["autoplay_on"] if new else m.lang["autoplay_off"])
