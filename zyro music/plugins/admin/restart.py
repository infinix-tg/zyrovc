# ==============================================================================
# restart.py - System Controls
# ==============================================================================
# Commands for grabbing logs and rebooting the bot.
# ==============================================================================

import os
import sys
import shutil
import asyncio

from pyrogram import filters, types

from HasiiMusic import app, db, lang, stop


@app.on_message(filters.command(["logs"]) & app.sudo_filter)
@lang.language()
async def _logs(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    sent = await m.reply_text(m.lang["log_fetch"])
    if not os.path.exists("log.txt"):
        return await sent.edit_text(m.lang["log_not_found"])
    
    # Read log file and extract logs from last bot start
    try:
        with open("log.txt", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Find the last occurrence of bot start marker (first log line of startup sequence)
        start_marker = "Cache directories updated."
        last_start_index = content.rfind(start_marker)
        
        if last_start_index != -1:
            # Get logs from the last bot start
            recent_logs = content[last_start_index:]
            
            # Write to temporary file
            temp_log_path = "temp_recent_logs.txt"
            with open(temp_log_path, "w", encoding="utf-8") as f:
                f.write(recent_logs)
            
            await sent.edit_media(
                media=types.InputMediaDocument(
                    media=temp_log_path,
                    caption=m.lang["log_sent"].format(app.name) + " (Last session)",
                )
            )
            
            # Clean up temp file
            try:
                os.remove(temp_log_path)
            except Exception:
                pass
        else:
            # If no start marker found, send the full log file
            await sent.edit_media(
                media=types.InputMediaDocument(
                    media="log.txt",
                    caption=m.lang["log_sent"].format(app.name),
                )
            )
    except Exception as e:
        await sent.edit_text(f"Error reading logs: {str(e)}")


@app.on_message(filters.command(["logger"]) & app.sudo_filter)
@lang.language()
async def _logger(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    if len(m.command) < 2:
        return await m.reply_text(m.lang["logger_usage"].format(m.command[0]))
    if m.command[1] not in ("on", "off"):
        return await m.reply_text(m.lang["logger_usage"].format(m.command[0]))

    if m.command[1] == "on":
        await db.set_logger(True)
        await m.reply_text(m.lang["logger_on"])
    else:
        await db.set_logger(False)
        await m.reply_text(m.lang["logger_off"])


@app.on_message(filters.command(["restart"]) & app.sudo_filter)
@lang.language()
async def _restart(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    sent = await m.reply_text(m.lang["restarting"])

    # Keep downloads to allow instant reuse after restart.
    for directory in ["cache"]:
        shutil.rmtree(directory, ignore_errors=True)

    await sent.edit_text(m.lang["restarted"])
    asyncio.create_task(stop())
    await asyncio.sleep(2)

    os.execl(sys.executable, sys.executable, "-m", "HasiiMusic")
