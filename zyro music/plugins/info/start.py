# ==============================================================================
# start.py - Basics
# ==============================================================================
# Essential user-facing commands: /start, /help, /settings, etc.
# ==============================================================================

from pyrogram import enums, filters, types

from HasiiMusic import app, config, db, lang, settings
from HasiiMusic.helpers import buttons, utils


@app.on_message(filters.command(["help"]) & filters.private & ~app.bl_users)
@lang.language()
async def _help(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    help_text = settings.render(settings.get("help_text"), m.from_user) or m.lang["help_menu"]
    await utils.reply_photo_or_text(
        m,
        settings.help_photo(),
        help_text,
        reply_markup=buttons.help_markup(m.lang),
    )


@app.on_message(filters.command(["start"]))
@lang.language()
async def start(_, message: types.Message):
    # Auto-delete command message in group chats
    if message.chat.type != enums.ChatType.PRIVATE:
        try:
            await message.delete()
        except Exception:
            pass
    
    # Skip if message from channel or anonymous admin
    if not message.from_user:
        return

    # Check if user is blacklisted
    if message.from_user.id in app.bl_users and message.from_user.id not in db.notified:
        return await message.reply_text(message.lang["bl_user_notify"])

    # If /start help, show help menu
    if len(message.command) > 1 and message.command[1] == "help":
        return await _help(_, message)

    # Determine if chat is private or group
    private = message.chat.type == enums.ChatType.PRIVATE

    # Welcome text and picture come from the owner panel (/panel)
    _text = settings.welcome(private, message.from_user)
    key = buttons.start_key(message.lang, private)
    await utils.reply_photo_or_text(
        message, settings.start_photo(), _text, reply_markup=key
    )

    # For private chats, add user to database if new
    if private:
        if await db.is_user(message.from_user.id):
            return  # User already exists, no need to add
        # Log new user to logger group
        await utils.send_log(message)
        # Add user to database
        return await db.add_user(message.from_user.id)


@app.on_message(filters.command(["playmode", "settings"]) & filters.group & ~app.bl_users)
@lang.language()
async def settings(_, message: types.Message):
    # Auto-delete command message
    try:
        await message.delete()
    except Exception:
        pass
    
    admin_only = await db.get_play_mode(message.chat.id)  # Get play mode setting
    _language = "en"
    await utils.safe_text(
        message,
        message.lang["start_settings"].format(message.chat.title),
        reply_markup=buttons.settings_markup(
            message.lang, admin_only, _language, message.chat.id
        ),
    )


@app.on_message(filters.new_chat_members, group=7)
@lang.language()
async def _new_member(_, message: types.Message):
    # Only work in supergroups (not basic groups)
    if message.chat.type != enums.ChatType.SUPERGROUP:
        return await message.chat.leave()

    # Check each new member
    for member in message.new_chat_members:
        if member.id == app.id:  # Bot itself was added
            if await db.is_chat(message.chat.id):
                return  # Chat already in database
            # Add chat to database (log is sent from new_chat.py with photo)
            await db.add_chat(message.chat.id)
