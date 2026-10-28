# ==============================================================================
# leave.py - Sudo Leave Controls
# ==============================================================================
# /leave to force the bot and assistant out of the current chat.
# /leaveall to kick assistants out of all inactive chats.
# ==============================================================================

import asyncio
from pyrogram import filters, types, errors, enums

from HasiiMusic import app, db, lang, logger, userbot, config


@app.on_message(filters.command(["leave"]) & app.sudo_filter)
@lang.language()
async def _leave(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    chat_id = m.chat.id
    chat_name = m.chat.title or "this chat"

    # Send confirmation message
    sent = await m.reply_text(
        f"<blockquote><b>Leaving Chat</b></blockquote>\n\n"
        f"<blockquote>Bot and assistant are leaving <b>{chat_name}</b>...</blockquote>"
    )

    # Try to make assistant leave if it's in the chat
    try:
        client = await db.get_client(chat_id)
        try:
            await client.leave_chat(chat_id)
        except errors.UserNotParticipant:
            # Assistant is not in the chat, skip
            pass
        except Exception as e:
            # Log any other errors but continue with bot leaving
            pass
    except Exception:
        # If getting client fails, just continue with bot leaving
        pass

    # Make bot leave the chat
    try:
        await app.leave_chat(chat_id)
    except Exception as e:
        # If bot can't leave, inform the sudo user
        await sent.edit_text(
            f"<blockquote><b>Error</b></blockquote>\n\n"
            f"<blockquote>Failed to leave chat: {str(e)}</blockquote>"
        )



from pyrogram.raw import functions, types as raw_types

async def get_valid_chats(client):
    chat_ids = set()
    offset_date = 0
    offset_id = 0
    offset_peer = raw_types.InputPeerEmpty()
    limit = 100
    
    while True:
        try:
            r = await client.invoke(
                functions.messages.GetDialogs(
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_peer=offset_peer,
                    limit=limit,
                    hash=0
                )
            )
        except Exception:
            break
            
        if not getattr(r, 'dialogs', None):
            break
            
        for chat in getattr(r, 'chats', []):
            if isinstance(chat, raw_types.Channel) and getattr(chat, 'megagroup', False):
                chat_ids.add(int(f"-100{chat.id}"))
            elif isinstance(chat, raw_types.Chat):
                chat_ids.add(-chat.id)
                
        last_dialog = r.dialogs[-1]
        peer = last_dialog.peer
        
        if isinstance(peer, raw_types.PeerChannel):
            access_hash = 0
            for c in getattr(r, 'chats', []):
                if isinstance(c, raw_types.Channel) and getattr(c, 'id', 0) == getattr(peer, 'channel_id', 0):
                    access_hash = getattr(c, 'access_hash', 0)
                    break
            offset_peer = raw_types.InputPeerChannel(channel_id=getattr(peer, 'channel_id', 0), access_hash=access_hash)
        elif isinstance(peer, raw_types.PeerChat):
            offset_peer = raw_types.InputPeerChat(chat_id=getattr(peer, 'chat_id', 0))
        elif isinstance(peer, raw_types.PeerUser):
            access_hash = 0
            for u in getattr(r, 'users', []):
                if isinstance(u, raw_types.User) and getattr(u, 'id', 0) == getattr(peer, 'user_id', 0):
                    access_hash = getattr(u, 'access_hash', 0)
                    break
            offset_peer = raw_types.InputPeerUser(user_id=getattr(peer, 'user_id', 0), access_hash=access_hash)
        else:
            break
            
        offset_id = getattr(last_dialog, 'top_message', 0)
        
    return list(chat_ids)

@app.on_message(filters.command(["leaveall"]) & app.sudo_filter)
@lang.language()
async def _leaveall(_, m: types.Message):
    # Auto-delete command message
    try:
        await m.delete()
    except Exception:
        pass
    
    sent = await m.reply_text(
        f"<blockquote><b>Processing...</b></blockquote>\n\n"
        f"<blockquote>Making assistants leave all inactive groups...</blockquote>"
    )
    
    total_left = 0
    
    for ub in userbot.clients:
        left = 0
        try:
            chat_ids = await get_valid_chats(ub)
            for chat_id in chat_ids:
                # Skip logger and excluded chats
                excluded = [app.logger] + config.EXCLUDED_CHATS
                if chat_id in excluded:
                    continue
                    
                # Skip if currently in an active call
                if chat_id in db.active_calls:
                    continue
                    
                try:
                    await ub.leave_chat(chat_id)
                    left += 1
                    total_left += 1
                    await asyncio.sleep(1)  # Rate limit
                except Exception as e:
                    logger.debug(f"Failed to leave {chat_id}: {e}")
                    continue
                        
        except Exception as e:
            logger.error(f"Error in leaveall for assistant {ub.me.username if hasattr(ub, 'me') and ub.me else 'Unknown'}: {e}")
            continue
    
    await sent.edit_text(
        f"<blockquote><b>Cleanup Complete</b></blockquote>\n\n"
        f"<blockquote>Assistants left <b>{total_left}</b> inactive groups.</blockquote>"
    )
